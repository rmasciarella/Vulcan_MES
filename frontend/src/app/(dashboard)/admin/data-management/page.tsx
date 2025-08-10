"use client";

import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataGrid, type DataGridRow } from "@/shared/components/data-table/DataGrid";
import { ImportModal } from "@/shared/components/data-table/ImportModal";
import { ConfirmationModal } from "@/shared/components/forms/ConfirmationModal";
// Replaced deprecated API functions with direct fetch calls

// Types for the example grid rows
export type Row = DataGridRow;

// API layer (reads/writes go through environment-based base URL or Netlify /api proxy)
async function fetchRows(params: {
  page: number;
  pageSize: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  filter?: string;
}): Promise<{ rows: Row[]; total: number }> {
  const qs = new URLSearchParams();
  qs.set("page", String(params.page));
  qs.set("pageSize", String(params.pageSize));
  if (params.sortBy) qs.set("sortBy", params.sortBy);
  if (params.sortDir) qs.set("sortDir", params.sortDir);
  if (params.filter) qs.set("filter", params.filter);
  
  // Example endpoint: GET /rows - using direct fetch
  const response = await fetch(`/api/rows?${qs.toString()}`);
  if (!response.ok) throw new Error(`GET /rows failed: ${response.status}`);
  return response.json();
}

async function patchRow(rowId: string, patch: Partial<Row>): Promise<Row> {
  // Example endpoint: PATCH /rows/:id - using direct fetch
  const response = await fetch(`/api/rows/${encodeURIComponent(rowId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(`PATCH /rows/${rowId} failed: ${response.status}`);
  return response.json();
}

async function ingestFile(file: File): Promise<{ ok: boolean; errors?: string[] }>{
  // Example endpoint: POST /ingest (multipart) - using direct fetch
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`/api/ingest`, {
    method: 'POST',
    body: form,
  });
  if (!response.ok) throw new Error(`UPLOAD /ingest failed: ${response.status}`);
  return response.json();
}

async function destructiveTruncate(): Promise<void> {
  // Example endpoint: POST /truncate - using direct fetch
  const response = await fetch(`/api/truncate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!response.ok) throw new Error(`POST /truncate failed: ${response.status}`);
}

export default function Page() {
  // Table state owned by the page so we can call APIs on changes
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortDir, setSortDir] = useState<"asc" | "desc" | undefined>();
  const [filter, setFilter] = useState<string>("");

  const queryClient = useQueryClient();

  const queryKey = useMemo(
    () => ["rows", { page, pageSize, sortBy, sortDir, filter }],
    [page, pageSize, sortBy, sortDir, filter]
  );

  const { data, isLoading, isFetching } = useQuery({
    queryKey,
    queryFn: () => fetchRows({ 
      page, 
      pageSize, 
      ...(sortBy !== undefined && { sortBy }), 
      ...(sortDir !== undefined && { sortDir }), 
      filter 
    }),
    placeholderData: (previousData) => previousData,
  });

  const patchMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<Row> }) => patchRow(id, patch),
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<{ rows: Row[]; total: number }>(queryKey);
      if (previous) {
        const optimistic: { rows: Row[]; total: number } = {
          total: previous.total,
          rows: previous.rows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
        };
        queryClient.setQueryData(queryKey, optimistic);
      }
      return { previous };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(queryKey, ctx.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  // Modals
  const [showImport, setShowImport] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const total = data?.total ?? 0;
  const rows = data?.rows ?? [];

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Data Management</h1>
        <div className="flex gap-2">
          <button
            className="border rounded px-3 py-1"
            onClick={() => setShowImport(true)}
          >
            Import CSV
          </button>
          <button
            className="border rounded px-3 py-1 text-red-700 hover:bg-red-50"
            onClick={() => setShowConfirm(true)}
          >
            Truncate All
          </button>
        </div>
      </div>

      <DataGrid
        rows={rows}
        total={total}
        page={page}
        pageSize={pageSize}
        loading={isLoading || isFetching}
        {...(sortBy !== undefined && { sortBy })}
        {...(sortDir !== undefined && { sortDir })}
        filter={filter}
        onPageChange={setPage}
        onPageSizeChange={(n) => {
          setPageSize(n);
          setPage(1);
        }}
        onSortChange={(col, dir) => {
          setSortBy(col);
          setSortDir(dir);
          setPage(1);
        }}
        onFilterChange={(val) => {
          setFilter(val);
          setPage(1);
        }}
        onRowUpdate={(id, patch) => patchMutation.mutate({ id, patch })}
      />

      {showImport && (
        <ImportModal
          onCancel={() => setShowImport(false)}
          onConfirm={async (file) => {
            const res = await ingestFile(file);
            if (res.ok) {
              setShowImport(false);
              // Refetch first page after import
              setPage(1);
              queryClient.invalidateQueries({ queryKey });
            } else {
              // You can surface res.errors in the modal as needed
              alert((res.errors ?? ["Unknown error"]).join("\n"));
            }
          }}
        />
      )}

      {showConfirm && (
        <ConfirmationModal
          title="Truncate all rows"
          getImpactDetails={async () => {
            // Hook to fetch counts/impacts to show in step 1
            // TODO: replace with a HEAD/GET call if you want real impact numbers
            await new Promise((r) => setTimeout(r, 150));
            return { rowsToDelete: total };
          }}
          onCancel={() => setShowConfirm(false)}
          onConfirm={async () => {
            await destructiveTruncate();
            setShowConfirm(false);
            setPage(1);
            queryClient.invalidateQueries({ queryKey });
          }}
        />
      )}
    </div>
  );
}