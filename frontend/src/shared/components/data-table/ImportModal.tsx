"use client";

import React from "react";

interface ImportModalProps {
  onCancel: () => void;
  onConfirm: (file: File) => Promise<void> | void;
}

export function ImportModal(props: ImportModalProps) {
  const [file, setFile] = React.useState<File | null>(null);
  const [preview, setPreview] = React.useState<string[][]>([]); // header + up to 10 rows
  const [parsing, setParsing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function handleFileChange(f: File) {
    setError(null);
    setFile(f);
    setParsing(true);
    try {
      const text = await f.text();
      const lines = text.split(/\r?\n/).filter(Boolean);
      const table = lines.slice(0, 11).map((line) => line.split(","));
      setPreview(table);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setParsing(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded shadow w-full max-w-2xl p-4 space-y-4">
        <div className="text-lg font-semibold">Import CSV</div>
        <div className="space-y-2">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) handleFileChange(file)
            }}
          />
          {parsing && <div className="text-sm text-gray-500">Parsing preview…</div>}
          {error && <div className="text-sm text-red-600">{error}</div>}
          {preview.length > 0 && (
            <div className="border rounded overflow-x-auto">
              <table className="min-w-full text-xs">
                <tbody>
                  {preview.map((row, i) => (
                    <tr key={i} className={i === 0 ? "bg-gray-50 font-semibold" : ""}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-2 py-1 border-t">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <div className="flex items-center justify-end gap-2">
          <button className="border rounded px-3 py-1" onClick={props.onCancel}>
            Cancel
          </button>
          <button
            className="border rounded px-3 py-1 bg-blue-600 text-white disabled:opacity-50"
            disabled={!file}
            onClick={async () => file && (await props.onConfirm(file))}
          >
            Import
          </button>
        </div>
      </div>
    </div>
  );
}