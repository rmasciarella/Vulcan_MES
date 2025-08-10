"use client";

import React from "react";

// Generic row type that can be extended for specific use cases
export interface DataGridRow {
  id: string;
  name: string;
  status: "active" | "inactive";
  [key: string]: any; // Allow additional properties
}

interface DataGridProps {
  rows: DataGridRow[];
  total: number;
  page: number;
  pageSize: number;
  loading?: boolean;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  filter: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onSortChange: (column: string, dir: "asc" | "desc") => void;
  onFilterChange: (value: string) => void;
  onRowUpdate: (id: string, patch: Partial<DataGridRow>) => void;
}

export function DataGrid(props: DataGridProps) {
  const { rows, total, page, pageSize, loading, sortBy, sortDir } = props;

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-3">
      <div className="flex gap-2 items-center">
        <input
          className="border rounded px-2 py-1 w-64"
          placeholder="Filter by name..."
          value={props.filter}
          onChange={(e) => props.onFilterChange(e.target.value)}
        />
        {loading && <span className="text-sm text-gray-500">Loading…</span>}
      </div>

      <div className="overflow-x-auto border rounded">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <Th
                label="ID"
                column="id"
                {...(sortBy !== undefined && { sortBy })}
                {...(sortDir !== undefined && { sortDir })}
                onSort={props.onSortChange}
              />
              <Th
                label="Name"
                column="name"
                {...(sortBy !== undefined && { sortBy })}
                {...(sortDir !== undefined && { sortDir })}
                onSort={props.onSortChange}
              />
              <Th
                label="Status"
                column="status"
                {...(sortBy !== undefined && { sortBy })}
                {...(sortDir !== undefined && { sortDir })}
                onSort={props.onSortChange}
              />
              <th className="text-left px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{r.id}</td>
                <td className="px-3 py-2">
                  <InlineEditable
                    value={r.name}
                    onChange={(val) => props.onRowUpdate(r.id, { name: val })}
                  />
                </td>
                <td className="px-3 py-2">
                  <select
                    className="border rounded px-2 py-1"
                    value={r.status}
                    onChange={(e) =>
                      props.onRowUpdate(r.id, { status: e.target.value as DataGridRow["status"] })
                    }
                  >
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                  </select>
                </td>
                <td className="px-3 py-2 text-gray-500">—</td>
              </tr>
            ))}
            {rows.length === 0 && !loading && (
              <tr>
                <td className="px-3 py-6 text-center text-gray-500" colSpan={4}>
                  No rows
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
          Page {page} / {totalPages} • {total} total
        </div>
        <div className="flex items-center gap-2">
          <button
            className="border rounded px-3 py-1 disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => props.onPageChange(page - 1)}
          >
            Prev
          </button>
          <button
            className="border rounded px-3 py-1 disabled:opacity-50"
            disabled={page >= totalPages}
            onClick={() => props.onPageChange(page + 1)}
          >
            Next
          </button>
          <select
            className="border rounded px-2 py-1"
            value={pageSize}
            onChange={(e) => props.onPageSizeChange(Number(e.target.value))}
          >
            {[10, 20, 50].map((n) => (
              <option key={n} value={n}>
                {n}/page
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

function Th(props: {
  label: string;
  column: string;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  onSort: (column: string, dir: "asc" | "desc") => void;
}) {
  const active = props.sortBy === props.column;
  const nextDir = !active ? "asc" : props.sortDir === "asc" ? "desc" : "asc";
  return (
    <th className="text-left px-3 py-2">
      <button
        className={`flex items-center gap-1 ${active ? "font-semibold" : ""}`}
        onClick={() => props.onSort(props.column, nextDir)}
      >
        {props.label}
        {active && (
          <span className="text-xs text-gray-500">{props.sortDir === "asc" ? "▲" : "▼"}</span>
        )}
      </button>
    </th>
  );
}

function InlineEditable({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [editing, setEditing] = React.useState(false);
  const [val, setVal] = React.useState(value);
  React.useEffect(() => setVal(value), [value]);

  return editing ? (
    <div className="flex items-center gap-2">
      <input
        className="border rounded px-2 py-1 w-full"
        value={val}
        onChange={(e) => setVal(e.target.value)}
      />
      <button
        className="border rounded px-2 py-1"
        onClick={() => {
          setEditing(false);
          if (val !== value) onChange(val);
        }}
      >
        Save
      </button>
      <button className="border rounded px-2 py-1" onClick={() => setEditing(false)}>
        Cancel
      </button>
    </div>
  ) : (
    <button className="text-left w-full" onClick={() => setEditing(true)}>
      {value}
    </button>
  );
}