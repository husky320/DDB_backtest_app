from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import dolphindb as ddb

from app.core.storage import read_json, write_json


@dataclass
class DDBNodeStatus:
    host: str
    port: int
    alias: str = ""
    can_load_dfs: bool = False
    available: bool = False
    error: str = ""


@dataclass
class DDBConfig:
    host: str = "183.134.101.135"
    port: int = 8030
    username: str = "admin"
    password: str = "123456"
    candidate_ports: list[int] = field(default_factory=lambda: [8030, 8031, 8032, 8033])
    preferred_data_node: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DDBConfig":
        return cls(
            host=str(payload.get("host", "183.134.101.135")),
            port=int(payload.get("port", 8030)),
            username=str(payload.get("username", "admin")),
            password=str(payload.get("password", "123456")),
            candidate_ports=[int(x) for x in payload.get("candidate_ports", [8030, 8031, 8032, 8033])],
            preferred_data_node=str(payload.get("preferred_data_node", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "candidate_ports": self.candidate_ports,
            "preferred_data_node": self.preferred_data_node,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "password": "",
            "candidate_ports": self.candidate_ports,
            "preferred_data_node": self.preferred_data_node,
            "has_password": bool(self.password),
        }


class DolphinDBConnectionManager:
    def __init__(self, config_file: Path) -> None:
        self._config_file = config_file
        self._lock = threading.Lock()
        self._controller_session: ddb.session | None = None
        self._data_sessions: dict[str, ddb.session] = {}
        self._data_node_endpoints: dict[str, tuple[str, int]] = {}
        self._node_status: list[DDBNodeStatus] = []
        self._active_data_node: str = ""
        self._last_probe_ts: float = 0.0
        self._config = self._load_config()

    def _load_config(self) -> DDBConfig:
        payload = read_json(self._config_file, {})
        return DDBConfig.from_dict(payload)

    def get_config(self) -> DDBConfig:
        return self._config

    def _has_usable_data_node(self, statuses: list[DDBNodeStatus]) -> bool:
        return any(status.available and status.can_load_dfs for status in statuses)

    def update_config(self, payload: dict[str, Any], validate_connection: bool = True) -> DDBConfig:
        previous = replace(self._config)
        merged = dict(payload)
        if not str(merged.get("password", "")).strip():
            merged["password"] = previous.password
        with self._lock:
            self._config = DDBConfig.from_dict(merged)
            write_json(self._config_file, self._config.to_dict())
            self._reset_sessions()
        if not validate_connection:
            return self._config
        statuses = self.probe_data_nodes(force=True)
        if self._has_usable_data_node(statuses):
            return self._config

        # Roll back if the new configuration cannot reach any usable data node.
        with self._lock:
            self._config = previous
            write_json(self._config_file, self._config.to_dict())
            self._reset_sessions()
        self.probe_data_nodes(force=True)
        raise RuntimeError("No available DolphinDB data node for the provided configuration.")

    def get_public_config(self) -> dict[str, Any]:
        return self._config.to_public_dict()

    def _reset_sessions(self) -> None:
        if self._controller_session is not None:
            try:
                self._controller_session.close()
            except Exception:
                pass
        self._controller_session = None
        for _, session in list(self._data_sessions.items()):
            try:
                session.close()
            except Exception:
                pass
        self._data_sessions = {}
        self._data_node_endpoints = {}
        self._node_status = []
        self._active_data_node = ""
        self._last_probe_ts = 0.0

    def _new_session(self, host: str, port: int) -> ddb.session:
        session = ddb.session(enablePickle=False)
        session.connect(
            host=host,
            port=port,
            userid=self._config.username,
            password=self._config.password,
        )
        return session

    def _ensure_controller_session(self) -> ddb.session:
        with self._lock:
            if self._controller_session is None:
                self._controller_session = self._new_session(self._config.host, self._config.port)
            return self._controller_session

    def _can_open_port(self, host: str, port: int, timeout_s: float = 1.0) -> bool:
        sock = socket.socket()
        sock.settimeout(timeout_s)
        try:
            sock.connect((host, port))
            return True
        except Exception:
            return False
        finally:
            sock.close()

    def _can_load_dfs(self, session: ddb.session) -> bool:
        try:
            session.run('exec count(*) from loadTable("dfs://day_singal","day_singal")')
            return True
        except Exception:
            return False

    def _is_not_data_node_error(self, text: str) -> bool:
        lowered = (text or "").lower()
        markers = [
            "isn't a data node",
            "is not a data node",
            "can't run function [loadtable]",
            "cannot run function [loadtable]",
            "not a data node",
            "不是数据节点",
        ]
        return any(token in lowered for token in markers)

    def _discover_hosts_from_cluster(self) -> list[str]:
        # 默认只探测配置主机，避免跨网络探测导致的长耗时。
        return [self._config.host]

    def probe_data_nodes(self, force: bool = False) -> list[DDBNodeStatus]:
        with self._lock:
            if not force and (time.time() - self._last_probe_ts) < 60 and self._node_status:
                return list(self._node_status)

        hosts = self._discover_hosts_from_cluster()
        statuses: list[DDBNodeStatus] = []
        sessions: dict[str, ddb.session] = {}
        endpoints: dict[str, tuple[str, int]] = {}

        for host in hosts:
            for port in self._config.candidate_ports:
                status = DDBNodeStatus(host=host, port=port)
                if not self._can_open_port(host, port):
                    status.error = "port unreachable"
                    statuses.append(status)
                    continue
                try:
                    session = self._new_session(host, port)
                    status.available = True
                    try:
                        status.alias = str(session.run("getNodeAlias()"))
                    except Exception:
                        status.alias = f"{host}:{port}"
                    status.can_load_dfs = self._can_load_dfs(session)
                    if status.can_load_dfs:
                        sessions[status.alias] = session
                        endpoints[status.alias] = (host, port)
                    else:
                        try:
                            session.close()
                        except Exception:
                            pass
                except Exception as exc:
                    status.error = str(exc)
                statuses.append(status)

        with self._lock:
            for _, session in list(self._data_sessions.items()):
                if session not in sessions.values():
                    try:
                        session.close()
                    except Exception:
                        pass
            self._data_sessions = sessions
            self._data_node_endpoints = endpoints
            self._node_status = statuses
            self._last_probe_ts = time.time()
            if self._config.preferred_data_node and self._config.preferred_data_node in sessions:
                self._active_data_node = self._config.preferred_data_node
            elif sessions:
                self._active_data_node = next(iter(sessions.keys()))
            else:
                self._active_data_node = ""
        return list(statuses)

    def get_status(self) -> dict[str, Any]:
        self.probe_data_nodes(force=False)
        with self._lock:
            has_usable_node = self._has_usable_data_node(self._node_status)
        if not has_usable_node:
            self.probe_data_nodes(force=True)
        with self._lock:
            return {
                "config": self._config.to_public_dict(),
                "active_data_node": self._active_data_node,
                "nodes": [status.__dict__ for status in self._node_status],
            }

    def _pick_data_session(self) -> ddb.session:
        self.probe_data_nodes(force=False)
        with self._lock:
            if self._active_data_node and self._active_data_node in self._data_sessions:
                return self._data_sessions[self._active_data_node]
            raise RuntimeError("No available data node. Check DolphinDB connection configuration.")

    def open_task_session(self, require_data_node: bool = True, force_probe: bool = False) -> ddb.session:
        if not require_data_node:
            return self._new_session(self._config.host, self._config.port)
        self.probe_data_nodes(force=force_probe)
        with self._lock:
            alias = self._active_data_node
            if not alias or alias not in self._data_node_endpoints:
                raise RuntimeError("No available data node. Check DolphinDB connection configuration.")
            # Try active node first, then fallback to other discovered data nodes.
            ordered_aliases: list[str] = [alias] + [
                key for key in self._data_node_endpoints.keys() if key != alias
            ]
            endpoints = dict(self._data_node_endpoints)

        last_error = "No available data node."
        for node_alias in ordered_aliases:
            host, port = endpoints[node_alias]
            session = None
            try:
                session = self._new_session(host, port)
                # Runtime validation to avoid accidentally landing on controller.
                session.run('exec count(*) from loadTable("dfs://day_singal","day_singal")')
                with self._lock:
                    self._active_data_node = node_alias
                return session
            except Exception as exc:
                last_error = str(exc)
                if session is not None:
                    try:
                        session.close()
                    except Exception:
                        pass
                continue
        raise RuntimeError(f"No available data node session. Last error: {last_error}")

    def execute(self, script: str, require_data_node: bool = True) -> Any:
        if require_data_node:
            session = self._pick_data_session()
        else:
            session = self._ensure_controller_session()
        try:
            return session.run(script)
        except Exception as exc:
            text = str(exc)
            if self._is_not_data_node_error(text):
                self.probe_data_nodes(force=True)
                retry_session = self.open_task_session(require_data_node=True, force_probe=True)
                try:
                    return retry_session.run(script)
                finally:
                    try:
                        retry_session.close()
                    except Exception:
                        pass
            if "connection has been closed" in text.lower():
                self.probe_data_nodes(force=True)
                retry_session = self._pick_data_session() if require_data_node else self._ensure_controller_session()
                return retry_session.run(script)
            raise
