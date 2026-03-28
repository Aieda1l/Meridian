import { type ReactNode } from 'react';

interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRowClick?: (row: T) => void;
  loading?: boolean;
}

export default function DataTable<T>({
  columns,
  data,
  keyField,
  page,
  totalPages,
  onPageChange,
  onRowClick,
  loading,
}: DataTableProps<T>) {
  return (
    <div className="neo-card" style={{ padding: 0, overflow: 'hidden' }}>
      <div className="overflow-x-auto">
        <table className="neo-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} className={col.className ?? ''}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-neo-muted">
                  Loading...
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-8 text-center text-neo-muted">
                  No data
                </td>
              </tr>
            ) : (
              data.map((row) => (
                <tr
                  key={String(row[keyField])}
                  onClick={() => onRowClick?.(row)}
                  className={onRowClick ? 'cursor-pointer' : ''}
                >
                  {columns.map((col) => (
                    <td key={col.key} className={col.className ?? ''}>
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-light">
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page === 1}
            className="neo-btn text-sm py-1 px-3"
          >
            Previous
          </button>
          <span className="text-xs text-neo-muted font-semibold">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
            className="neo-btn text-sm py-1 px-3"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
