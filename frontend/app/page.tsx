"use client";

import { useEffect, useMemo, useState } from "react";

type WatchlistRow = {
  ticker: string;
  company: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
};

type TopMover = {
  date: string;
  ticker: string;
  change_percent: number;
  absolute_change: number;
  closing_price: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_STOCK_API_BASE_URL?.replace(/\/$/, "") ?? "";

const WATCHLIST_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"];

function formatCurrency(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatSignedCurrency(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }

  return `${value >= 0 ? "+" : "-"}${formatCurrency(Math.abs(value))}`;
}

function formatSignedPercent(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }

  return `${value >= 0 ? "+" : "-"}${Math.abs(value).toFixed(2)}%`;
}

function formatVolume(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "—";
  }

  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(1)}B`;
  }

  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }

  return value.toLocaleString("en-US");
}

function formatHistoryDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(parsed);
}

function formatLongDate(value: string) {
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function getChangeClasses(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "text-black/50";
  }

  return value >= 0
    ? "text-[var(--color-positive)]"
    : "text-[var(--color-negative)]";
}

function buildApiUrl(path: string) {
  if (!API_BASE_URL) {
    return null;
  }

  return `${API_BASE_URL}${path}`;
}

async function fetchJson<T>(path: string): Promise<T> {
  const url = buildApiUrl(path);

  if (!url) {
    throw new Error(
      "Missing NEXT_PUBLIC_STOCK_API_BASE_URL. Set it to your API Gateway base URL.",
    );
  }

  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export default function Home() {
  const [searchValue, setSearchValue] = useState("");

  const [watchlist, setWatchlist] = useState<WatchlistRow[]>([]);
  const [watchlistLoading, setWatchlistLoading] = useState(true);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  const [historyMovers, setHistoryMovers] = useState<TopMover[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialData() {
      setWatchlistLoading(true);
      setHistoryLoading(true);
      setWatchlistError(null);
      setHistoryError(null);

      const [watchlistResult, historyResult] = await Promise.allSettled([
        fetchJson<{ watchlist: WatchlistRow[] }>("/watchlist"),
        fetchJson<{ movers: TopMover[] }>("/top-movers?days=7"),
      ]);

      if (!isMounted) {
        return;
      }

      if (watchlistResult.status === "fulfilled") {
        setWatchlist(watchlistResult.value.watchlist ?? []);
      } else {
        console.error("Failed to load watchlist data", watchlistResult.reason);
        setWatchlistError(
          watchlistResult.reason instanceof Error
            ? watchlistResult.reason.message
            : "Unable to load watchlist data right now.",
        );
      }

      if (historyResult.status === "fulfilled") {
        setHistoryMovers(historyResult.value.movers ?? []);
      } else {
        console.error("Failed to load top mover history", historyResult.reason);
        setHistoryError(
          historyResult.reason instanceof Error
            ? historyResult.reason.message
            : "Unable to load top mover history right now.",
        );
      }

      setWatchlistLoading(false);
      setHistoryLoading(false);
    }

    loadInitialData();

    return () => {
      isMounted = false;
    };
  }, []);

  const latestMover = historyMovers[0] ?? null;

  const watchlistCompanyMap = useMemo(
    () => new Map(watchlist.map((row) => [row.ticker, row.company] as const)),
    [watchlist],
  );


  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#ffffff_0%,#f7f6f2_45%,#ece9df_100%)] text-foreground">
      <header className="sticky top-0 z-20 border-b border-black/10 bg-(--color-teal) shadow-[0_10px_30px_rgba(0,0,0,0.08)]">
        <div className="mx-auto w-full max-w-7xl px-5 py-6 sm:px-8 sm:py-8">
          <h1 className="font-mono text-4xl font-semibold tracking-[0.12em] text-white sm:text-6xl md:text-7xl">
            Stock Watchlist
          </h1>
        </div>
      </header>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-12 px-5 py-8 sm:px-8 sm:py-10">
        <section className="rounded-4xl border border-black/10 bg-white/80 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.06)] backdrop-blur sm:p-8">
          <div className="flex flex-col gap-6">
            <div className="flex flex-col gap-4">
              <h2 className="text-2xl font-semibold">My Watchlist</h2>

              <div className="relative w-full max-w-sm">
                <input
                  value={searchValue}
                  onChange={(event) => setSearchValue(event.target.value)}
                  placeholder="Add new"
                  aria-label="Add new ticker"
                  className="h-12 w-full rounded-full border border-black/15 bg-white px-4 pr-12 text-base outline-none transition focus:border-(--color-teal)"
                />
                <span className="pointer-events-none absolute inset-y-0 right-4 flex items-center text-black/60">
                  <svg
                    className="h-5 w-5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="m20 20-3.5-3.5" />
                  </svg>
                </span>
              </div>

              <div className="flex flex-wrap gap-3">
                {WATCHLIST_TICKERS.map((ticker) => (
                  <button
                    key={ticker}
                    type="button"
                    className="rounded-full bg-(--color-teal) px-4 py-1.5 text-sm font-semibold tracking-[0.08em] text-white shadow-[0_8px_20px_rgba(0,153,170,0.18)] transition hover:-translate-y-0.5"
                  >
                    {ticker}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <h3 className="text-2xl font-semibold">Watchlist Performance</h3>

              {watchlistError ? (
                <div className="rounded-3xl border border-(--color-negative)/20 bg-(--color-negative)/5 px-4 py-3 text-sm text-(--color-negative)">
                  {watchlistError}
                </div>
              ) : null}

              <div className="overflow-hidden rounded-3xl border border-black/10 bg-white">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm sm:text-base">
                    <thead className="bg-black/5 text-sm font-semibold uppercase tracking-[0.08em] text-black/70">
                      <tr>
                        {[
                          "Ticker",
                          "Company",
                          "Price",
                          "Change",
                          "% Change",
                          "Volume",
                        ].map((label) => (
                          <th key={label} className="px-4 py-4">
                            {label}
                          </th>
                        ))}
                      </tr>
                    </thead>

                    <tbody>
                      {watchlistLoading
                        ? WATCHLIST_TICKERS.map((ticker) => (
                            <tr key={ticker} className="border-t border-black/8">
                              {Array.from({ length: 7 }).map((_, index) => (
                                <td key={`${ticker}-${index}`} className="px-4 py-4">
                                  <div className="h-5 animate-pulse rounded-full bg-black/8" />
                                </td>
                              ))}
                            </tr>
                          ))
                        : watchlist.map((row) => (
                            <tr
                              key={row.ticker}
                              className="border-t border-black/8 transition hover:bg-black/2"
                            >
                              <td className="px-4 py-4 font-semibold">{row.ticker}</td>
                              <td className="px-4 py-4">{row.company}</td>
                              <td className="px-4 py-4">{formatCurrency(row.price)}</td>
                              <td className={`px-4 py-4 font-semibold ${getChangeClasses(row.change)}`}>
                                {formatSignedCurrency(row.change)}
                              </td>
                              <td
                                className={`px-4 py-4 font-semibold ${getChangeClasses(row.change_percent)}`}
                              >
                                {formatSignedPercent(row.change_percent)}
                              </td>
                              <td className="px-4 py-4">{formatVolume(row.volume)}</td>
                            </tr>
                          ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="rounded-4xl border border-black/10 bg-white/80 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.06)] backdrop-blur sm:p-8">
            <div className="flex flex-col gap-4">
              <h2 className="text-2xl font-semibold">
                Today&apos;s Greatest Mover, Highest % Change
                {latestMover ? ` (At close: ${formatLongDate(latestMover.date)})` : ""}
              </h2>

              {historyError ? (
                <div className="rounded-3xl border border-(--color-negative)/20 bg-(--color-negative)/5 px-4 py-3 text-sm text-(--color-negative)">
                  {historyError}
                </div>
              ) : null}

              <div className="rounded-[1.75rem] bg-(--color-surface) p-6">
                {historyLoading ? (
                  <div className="space-y-4">
                    <div className="h-10 w-28 animate-pulse rounded-full bg-black/8" />
                    <div className="h-7 w-44 animate-pulse rounded-full bg-black/8" />
                    <div className="h-12 w-36 animate-pulse rounded-full bg-black/8" />
                  </div>
                ) : latestMover ? (
                  <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-2">
                      <div className="text-5xl font-semibold">{latestMover.ticker}</div>
                      <div className="text-xl text-black/70">
                        {watchlistCompanyMap.get(latestMover.ticker) ?? latestMover.ticker}
                      </div>
                    </div>

                    <div className="flex flex-1 flex-col gap-4 md:items-end">
                      <div className="text-4xl font-semibold">
                        {formatCurrency(latestMover.closing_price)}
                      </div>
                      <div
                        className={`flex items-center gap-4 text-3xl font-semibold ${getChangeClasses(
                          latestMover.change_percent,
                        )}`}
                      >
                        <div className="flex flex-col gap-1 text-right text-xl sm:text-2xl">
                          <span>{formatSignedPercent(latestMover.change_percent)}</span>
                        </div>

                        <svg
                          viewBox="0 0 64 64"
                          className="h-14 w-14"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          aria-hidden="true"
                        >
                          {latestMover.change_percent >= 0 ? (
                            <path d="M12 44 28 28l10 10 14-14M42 24h10v10" />
                          ) : (
                            <path d="m12 20 16 16 10-10 14 14M42 40h10V30" />
                          )}
                        </svg>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-black/60">No mover data is available yet.</div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-4xl border border-black/10 bg-white/80 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.06)] backdrop-blur sm:p-8">
            <div className="flex flex-col gap-4">
              <h2 className="text-2xl font-semibold">Greatest Mover History (7 days)</h2>

              <div className="overflow-hidden rounded-3xl border border-black/10 bg-white">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm sm:text-base">
                    <thead className="bg-black/5 text-sm font-semibold uppercase tracking-[0.08em] text-black/70">
                      <tr>
                        <th className="px-4 py-4">Date</th>
                        <th className="px-4 py-4">Stock</th>
                        <th className="px-4 py-4">Change</th>
                        <th className="px-4 py-4">Close Price</th>
                      </tr>
                    </thead>

                    <tbody>
                      {historyLoading
                        ? Array.from({ length: 5 }).map((_, index) => (
                            <tr key={index} className="border-t border-black/8">
                              {Array.from({ length: 4 }).map((__, cellIndex) => (
                                <td key={cellIndex} className="px-4 py-4">
                                  <div className="h-5 animate-pulse rounded-full bg-black/8" />
                                </td>
                              ))}
                            </tr>
                          ))
                        : historyMovers.map((mover) => (
                            <tr
                              key={`${mover.date}-${mover.ticker}`}
                              className="border-t border-black/8 transition hover:bg-black/2"
                            >
                              <td className="px-4 py-4">{formatHistoryDate(mover.date)}</td>
                              <td className="px-4 py-4 font-semibold">{mover.ticker}</td>
                              <td
                                className={`px-4 py-4 font-semibold ${getChangeClasses(
                                  mover.change_percent,
                                )}`}
                              >
                                {formatSignedPercent(mover.change_percent)}
                              </td>
                              <td className="px-4 py-4">
                                {formatCurrency(mover.closing_price)}
                              </td>
                            </tr>
                          ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
