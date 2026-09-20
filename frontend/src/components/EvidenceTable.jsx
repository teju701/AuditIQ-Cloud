import { useEffect, useMemo, useState } from "react";

function _safeText(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function _sortValue(value) {
  if (value === null || value === undefined || value === "") return null;

  if (typeof value === "number") return value;
  if (typeof value === "boolean") return value ? 1 : 0;

  const text = String(value).trim();
  if (!text) return null;

  const numeric = Number(text.replaceAll(",", ""));
  if (!Number.isNaN(numeric) && text.match(/^[+-]?[0-9,.]+$/)) return numeric;

  const asDate = Date.parse(text);
  if (!Number.isNaN(asDate) && /[-/:T]/.test(text)) return asDate;

  return text.toLowerCase();
}

function _compareValues(left, right) {
  const leftValue = _sortValue(left);
  const rightValue = _sortValue(right);

  if (leftValue === rightValue) return 0;
  if (leftValue === null) return 1;
  if (rightValue === null) return -1;

  if (typeof leftValue === "number" && typeof rightValue === "number") {
    return leftValue - rightValue;
  }

  return String(leftValue).localeCompare(String(rightValue), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

export default function EvidenceTable({
  records,
  columns,
  rowCount,
  highlightedColumns = [],
  pagination,
  onPageChange,
  pageLoading = false,
}) {
  const safeRecords = Array.isArray(records) ? records : [];
  const allColumns = useMemo(() => {
    if (Array.isArray(columns) && columns.length > 0) return columns;
    if (safeRecords.length > 0) return Object.keys(safeRecords[0]);
    return [];
  }, [columns, safeRecords]);

  const [visibleColumns, setVisibleColumns] = useState(
    allColumns.slice(0, Math.min(8, allColumns.length)),
  );
  const [sortConfig, setSortConfig] = useState({ column: null, direction: "asc" });
  const [selectedRow, setSelectedRow] = useState(null);

  useEffect(() => {
    setVisibleColumns(allColumns.slice(0, Math.min(8, allColumns.length)));
    setSortConfig({ column: null, direction: "asc" });
    setSelectedRow(null);
  }, [allColumns]);

  const highlightSet = useMemo(
    () => new Set((highlightedColumns || []).map((col) => String(col))),
    [highlightedColumns],
  );

  const activeColumns = useMemo(() => {
    const filtered = visibleColumns.filter((col) => allColumns.includes(col));
    if (filtered.length > 0) return filtered;
    return allColumns.length > 0 ? [allColumns[0]] : [];
  }, [allColumns, visibleColumns]);

  const sortedRecords = useMemo(() => {
    if (!sortConfig.column) return safeRecords;

    const sorted = [...safeRecords].sort((a, b) => {
      const comparison = _compareValues(a?.[sortConfig.column], b?.[sortConfig.column]);
      return sortConfig.direction === "asc" ? comparison : -comparison;
    });

    return sorted;
  }, [safeRecords, sortConfig]);

  if (!safeRecords.length) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 p-4 text-center">
        <p className="text-xs text-gray-500">No evidence rows returned for this answer.</p>
      </div>
    );
  }

  const toggleColumn = (column) => {
    setVisibleColumns((current) => {
      if (current.includes(column)) {
        if (current.length === 1) return current;
        return current.filter((item) => item !== column);
      }

      return allColumns.filter((item) => item === column || current.includes(item));
    });
  };

  const toggleSort = (column) => {
    setSortConfig((current) => {
      if (current.column !== column) {
        return { column, direction: "asc" };
      }
      return {
        column,
        direction: current.direction === "asc" ? "desc" : "asc",
      };
    });
  };

  const sortLabel = sortConfig.column
    ? `${sortConfig.column} (${sortConfig.direction})`
    : "none";

  const currentPage = Number(pagination?.page || 1);
  const pageSize = Number(
    pagination?.page_size || safeRecords.length || Math.max(1, Number(rowCount || 0)),
  );
  const totalRows = Number(pagination?.total_rows || rowCount || safeRecords.length);
  const totalPages = Number(
    pagination?.total_pages || (totalRows > 0 ? Math.ceil(totalRows / Math.max(1, pageSize)) : 1),
  );

  const startRow = totalRows === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
  const endRow = totalRows === 0
    ? 0
    : Math.min((currentPage - 1) * pageSize + sortedRecords.length, totalRows);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <p className="text-xs text-gray-500">
          Showing {startRow}-{endRow} of {totalRows} matching record
          {totalRows !== 1 ? "s" : ""} · Sorted by {sortLabel}
        </p>

        <details className="text-xs">
          <summary className="cursor-pointer text-indigo-600 hover:text-indigo-800">
            Columns ({activeColumns.length}/{allColumns.length})
          </summary>
          <div className="mt-2 rounded-lg border border-gray-200 bg-white p-2 max-h-40 overflow-auto shadow-sm">
            {allColumns.map((column) => (
              <label key={column} className="flex items-center gap-2 py-1 text-gray-700">
                <input
                  type="checkbox"
                  checked={activeColumns.includes(column)}
                  onChange={() => toggleColumn(column)}
                />
                <span>{column}</span>
              </label>
            ))}
          </div>
        </details>
      </div>

      {highlightSet.size > 0 && (
        <p className="text-[11px] text-amber-700 mb-2">
          Highlighted fields are directly used in the computed evidence path.
        </p>
      )}

      <div className="overflow-x-auto rounded-xl border border-gray-200">
        <table className="w-full text-xs">
          <thead className="bg-gray-50 text-gray-500 uppercase tracking-wide">
            <tr>
              {activeColumns.map((column, idx) => {
                const sorted = sortConfig.column === column;
                return (
                  <th
                    key={column}
                    className={`px-3 py-2 text-left font-medium whitespace-nowrap ${idx === 0 ? "sticky left-0 bg-gray-50 z-10" : ""}`}
                  >
                    <button
                      onClick={() => toggleSort(column)}
                      className="inline-flex items-center gap-1 hover:text-indigo-700"
                    >
                      <span>{column}</span>
                      <span className="text-[10px]">
                        {sorted ? (sortConfig.direction === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sortedRecords.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                onClick={() => setSelectedRow(row)}
                className="hover:bg-indigo-50 transition-colors cursor-pointer"
              >
                {activeColumns.map((column, colIndex) => {
                  const highlighted = highlightSet.has(column);
                  const stickyClass = colIndex === 0 ? "sticky left-0 bg-white group-hover:bg-indigo-50" : "";
                  const highlightedClass = highlighted
                    ? "bg-amber-50 text-amber-900 font-medium"
                    : "text-gray-700";

                  return (
                    <td
                      key={column}
                      className={`px-3 py-2 whitespace-nowrap ${highlightedClass} ${stickyClass}`}
                    >
                      {_safeText(row?.[column])}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <p className="text-xs text-gray-500">
          Page {currentPage} of {totalPages}
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onPageChange?.(currentPage - 1)}
            disabled={pageLoading || currentPage <= 1}
            className="text-xs rounded-md border border-gray-300 px-2.5 py-1 text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <button
            onClick={() => onPageChange?.(currentPage + 1)}
            disabled={pageLoading || currentPage >= totalPages}
            className="text-xs rounded-md border border-gray-300 px-2.5 py-1 text-gray-600 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      </div>

      {pageLoading && (
        <p className="text-xs text-indigo-600 mt-2">Loading page...</p>
      )}

      {selectedRow && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button
            className="absolute inset-0 bg-black/35"
            onClick={() => setSelectedRow(null)}
            aria-label="Close row inspector"
          />
          <div className="relative h-full w-full max-w-lg bg-white border-l border-gray-200 shadow-xl overflow-y-auto">
            <div className="p-4 border-b border-gray-200 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-gray-800">Evidence row inspector</p>
                <p className="text-xs text-gray-500">Review all available fields for this record.</p>
              </div>
              <button
                onClick={() => setSelectedRow(null)}
                className="text-xs px-2.5 py-1 rounded-md border border-gray-300 text-gray-600 hover:bg-gray-100"
              >
                Close
              </button>
            </div>

            <div className="p-4 space-y-2">
              {allColumns.map((column) => (
                <div key={column} className="rounded-lg border border-gray-200 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-gray-500">{column}</p>
                  <p className="text-sm text-gray-800 wrap-break-word mt-0.5">{_safeText(selectedRow[column])}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
