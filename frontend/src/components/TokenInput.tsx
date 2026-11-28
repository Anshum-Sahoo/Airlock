/**
 * Reviewer token input.
 * Keeps the token in React state (page-memory) only.
 * NEVER: localStorage, sessionStorage, cookies, URLs, NEXT_PUBLIC_* env, logs.
 * On page reload the reviewer must re-enter the token.
 */

"use client";

import { useState } from "react";

interface TokenInputProps {
  onTokenSet: (token: string) => void;
  hasToken: boolean;
}

export function TokenInput({ onTokenSet, hasToken }: TokenInputProps) {
  const [draft, setDraft] = useState("");
  const [visible, setVisible] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = draft.trim();
    if (trimmed) {
      onTokenSet(trimmed);
      setDraft("");  // clear the input after setting
    }
  }

  if (hasToken) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[rgba(34,197,94,0.08)] border border-[rgba(34,197,94,0.3)] rounded text-xs">
        <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" />
        <span className="text-[#22C55E] font-semibold uppercase tracking-widest">Token set</span>
        <button
          onClick={() => onTokenSet("")}
          className="ml-2 text-[#52525B] hover:text-[#EF492F] transition-colors text-xs"
          title="Clear reviewer token"
        >
          ✕ Clear
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <div className="relative">
        <input
          type={visible ? "text" : "password"}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Reviewer token…"
          autoComplete="off"
          className="
            w-52 px-3 py-1.5 bg-[#F8F9FA] border border-[#E5E6E8] rounded
            text-xs text-[#191A1C] placeholder-[#52525B] font-mono
            focus:outline-none focus:border-[#EF492F] focus:shadow-[0_0_0_1px_#EF492F]
            transition-all
          "
          aria-label="Reviewer bearer token"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-[#52525B] hover:text-[#191A1C] text-xs"
          tabIndex={-1}
          aria-label={visible ? "Hide token" : "Show token"}
        >
          {visible ? "🙈" : "👁"}
        </button>
      </div>
      <button
        type="submit"
        disabled={!draft.trim()}
        className="
          px-3 py-1.5 text-xs font-semibold rounded
          bg-[#EF492F] text-white
          hover:bg-[#EF492F] hover:shadow-[0_0_12px_rgba(239,73,47,0.22)]
          disabled:opacity-40 disabled:cursor-not-allowed
          transition-all
        "
      >
        Set Token
      </button>
      <span className="text-[10px] text-[#52525B] ml-1">
        Stored in page memory only. Lost on reload.
      </span>
    </form>
  );
}
