"use client";
import { useState } from "react";
console.log("✅ Dombra page loaded");

type TabNote = { pitch:number; start:number; end:number; string:1|2; fret:number };

export default function Home() {
  const [tabs, setTabs] = useState<TabNote[]|null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string|null>(null);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 2_000_000) {
      setError("Keep it short (≤15 s).");
      return;
    }
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", f);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/transcribe`, {
        method: "POST",
        body: fd,
      });
      const json = await res.json();
      setTabs(json.tabs);
    } catch (err) {
      console.error(err);
      setError("Backend not reachable. Is FastAPI running?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="p-8 max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🎵 Dombra Tab Generator</h1>
      <input
        type="file"
        accept="audio/*"
        onChange={onUpload}
        className="border p-2 rounded-md bg-gray-50"
      />
      {loading && <p className="mt-4 text-blue-600">Transcribing…</p>}
      {error && <p className="mt-4 text-red-500">{error}</p>}
      {tabs && <TabTable tabs={tabs} />}
    </main>
  );
}

function TabTable({ tabs }: { tabs: TabNote[] }) {
  return (
    <div className="mt-6">
      <h2 className="font-semibold mb-2">Tab (DG dombra)</h2>
      <div className="font-mono text-sm whitespace-pre">
        {asciiTab(tabs)}
      </div>
    </div>
  );
}

function asciiTab(tabs: TabNote[]) {
  const wrapLength = 40; // number of tab positions per line before wrapping
  let s1: string[] = [];
  let s2: string[] = [];
  let output = "";

  tabs.forEach((n) => {
    const mark = String(n.fret).padEnd(3);
    if (n.string === 1) {
      s1.push(mark);
      s2.push("-- ");
    } else {
      s1.push("-- ");
      s2.push(mark);
    }

    // wrap every `wrapLength` notes
    if (s1.length >= wrapLength) {
      output += `G| ${s2.join("")}\nD| ${s1.join("")}\n\n`;
      s1 = [];
      s2 = [];
    }
  });

  // add remaining notes
  if (s1.length > 0) {
    output += `G| ${s2.join("")}\nD| ${s1.join("")}\n`;
  }

  return output;
}
