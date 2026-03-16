import React from "react";

interface ChipGroupProps {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}

export function ChipGroup({ options, selected, onChange }: ChipGroupProps) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((item) => item !== value));
      return;
    }
    onChange([...selected, value]);
  };

  return (
    <div className="chip-grid">
      {options.map((item) => (
        <button
          key={item}
          type="button"
          className={selected.includes(item) ? "chip active" : "chip"}
          onClick={() => toggle(item)}
        >
          {item}
        </button>
      ))}
    </div>
  );
}

