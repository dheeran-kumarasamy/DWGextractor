import { useState } from "react";

interface ExtractResult {
  source_unit: string;
  is_imperial: boolean;
  warnings: string[];
  legend: Array<{ label: string; role: string; signature: Record<string, unknown> }>;
  wall_types: Array<{
    label: string;
    role: string;
    thickness_mm: number;
    segment_lengths_mm: number[];
    count: number;
  }>;
  columns: Array<{ label: string; thickness_mm: number; count: number }>;
}

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    if (!file) {
      setError("Please choose a DWG or DXF file.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const response = await fetch("/extract", {
        method: "POST",
        body: form,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Failed to extract file.");
      }
      setResult(await response.json());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="mx-auto max-w-4xl rounded-3xl bg-white p-8 shadow-xl">
        <h1 className="text-3xl font-semibold text-slate-900">DWG Floor Plan Extractor</h1>
        <p className="mt-3 text-slate-600">
          Upload a DWG or DXF and receive a wall-by-hatch type report with legend decoding.
        </p>

        <div className="mt-6 flex flex-col gap-4">
          <input
            type="file"
            accept=".dwg,.dxf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="rounded-xl border border-slate-200 p-3"
          />
          <button
            type="button"
            onClick={submit}
            disabled={loading}
            className="inline-flex items-center justify-center rounded-2xl bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-400"
          >
            {loading ? "Uploading..." : "Extract"}
          </button>
          {error ? <div className="rounded-2xl bg-rose-100 p-4 text-sm text-rose-800">{error}</div> : null}
        </div>

        {result ? (
          <div className="mt-10 space-y-8">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="rounded-3xl bg-slate-100 p-6">
                <h2 className="text-lg font-semibold">Source units</h2>
                <p>{result.source_unit}</p>
                <p>{result.is_imperial ? "Imperial" : "Metric"}</p>
              </div>
              <div className="rounded-3xl bg-slate-100 p-6">
                <h2 className="text-lg font-semibold">Warnings</h2>
                <ul className="list-disc pl-5 text-sm text-slate-700">
                  {result.warnings.length ? (
                    result.warnings.map((warning, idx) => <li key={idx}>{warning}</li>)
                  ) : (
                    <li>No warnings.</li>
                  )}
                </ul>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-3xl bg-slate-100 p-6">
                <h2 className="text-lg font-semibold">Legend</h2>
                {result.legend.length ? (
                  <ul className="space-y-3">
                    {result.legend.map((entry) => (
                      <li key={entry.label} className="rounded-2xl bg-white p-4 shadow-sm">
                        <p className="font-semibold">{entry.label}</p>
                        <p className="text-sm text-slate-600">Role: {entry.role}</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No legend rows decoded.</p>
                )}
              </div>

              <div className="rounded-3xl bg-slate-100 p-6">
                <h2 className="text-lg font-semibold">Columns</h2>
                {result.columns.length ? (
                  <ul className="space-y-3">
                    {result.columns.map((column) => (
                      <li key={column.label} className="rounded-2xl bg-white p-4 shadow-sm">
                        <p className="font-semibold">{column.label}</p>
                        <p className="text-sm text-slate-600">Count: {column.count}</p>
                        <p className="text-sm text-slate-600">Thickness: {column.thickness_mm} mm</p>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>No columns detected.</p>
                )}
              </div>
            </div>

            <div className="rounded-3xl bg-slate-100 p-6">
              <h2 className="text-lg font-semibold">Wall types</h2>
              {result.wall_types.length ? (
                <div className="space-y-4">
                  {result.wall_types.map((wall) => (
                    <div key={wall.label} className="rounded-2xl bg-white p-4 shadow-sm">
                      <p className="font-semibold">{wall.label}</p>
                      <p className="text-sm text-slate-600">Role: {wall.role}</p>
                      <p className="text-sm text-slate-600">Count: {wall.count}</p>
                      <p className="text-sm text-slate-600">Thickness: {wall.thickness_mm} mm</p>
                      <p className="text-sm text-slate-600">Segments: {wall.segment_lengths_mm.join(", ")} mm</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p>No wall types extracted.</p>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default App;
