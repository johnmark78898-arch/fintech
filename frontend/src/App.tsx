import { useEffect, useMemo, useRef, useState } from "react";
import Papa from "papaparse";
import {
  Activity,
  ArrowDownLeft,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Check,
  ChevronDown,
  CircleHelp,
  Clock3,
  Database,
  FileText,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  MessageSquareText,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type View = "overview" | "transactions" | "analysis" | "forecast" | "documents" | "assistant" | "models";

type Transaction = {
  occurred_at: string;
  account_name: string;
  amount: string;
  currency: string;
  direction: "inflow" | "outflow";
  description: string;
  category: string;
  external_ref: string;
  invoice_id?: string;
  product_code?: string;
  quantity?: number;
  unit_price?: number;
  country?: string;
  line_total?: number;
  is_return?: boolean;
  invoice_month?: string;
  invoice_weekday?: string;
  invoice_hour?: number;
};

type DatasetContext = {
  source_kind: "demo" | "local";
  source_name: string;
  transaction_count: number;
  undated_count: number;
  currencies: { currency: string; inflow: number; outflow: number; transactions: number }[];
  monthly: { month: string; currency: string; inflow: number; outflow: number }[];
  categories: { category: string; currency: string; inflow: number; outflow: number; transactions: number }[];
};

type PublicSource = {
  source_id: string;
  title: string;
  publisher: string;
  url: string;
  edition: string;
  rights_basis: string;
  retrieved_at: string;
  chunk_count: number;
};

type PublicLibraryStatus = {
  status: string;
  source_count: number;
  chunk_count: number;
  retrieved_at: string;
  sources: PublicSource[];
};

type PublicSearchResult = {
  chunk_id: string;
  title: string;
  publisher: string;
  url: string;
  edition: string;
  retrieved_at: string;
  section: string;
  excerpt: string;
};

type GroundedAnswer = {
  answer: string;
  citations: PublicSearchResult[];
  abstained: boolean;
  data_based: boolean;
  model: string;
};

function isGroundedAnswer(value: unknown): value is GroundedAnswer {
  if (typeof value !== "object" || value === null || !("answer" in value) || !("citations" in value)) return false;
  return typeof value.answer === "string"
    && "abstained" in value
    && typeof value.abstained === "boolean"
    && "data_based" in value
    && typeof value.data_based === "boolean"
    && "model" in value
    && typeof value.model === "string"
    && Array.isArray(value.citations)
    && value.citations.every((citation) =>
      typeof citation === "object"
      && citation !== null
      && "chunk_id" in citation
      && typeof citation.chunk_id === "string"
      && "title" in citation
      && typeof citation.title === "string"
      && "url" in citation
      && typeof citation.url === "string");
}

const viewTitles: Record<View, string> = {
  overview: "Overview",
  transactions: "Transactions",
  analysis: "Analysis",
  forecast: "Cash flow",
  documents: "Documents",
  assistant: "AI assistant",
  models: "Model lab",
};

const navigation: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "transactions", label: "Transactions", icon: Activity },
  { id: "analysis", label: "Analysis", icon: BarChart3 },
  { id: "forecast", label: "Cash flow", icon: BarChart3 },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "assistant", label: "AI assistant", icon: MessageSquareText },
];

function formatMoney(value: number, currency = "GBP", fractionDigits = 0) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

function formatTransactionAmount(value: number, currency: string) {
  if (currency === "XXX") {
    return `${new Intl.NumberFormat("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)} (currency unknown)`;
  }
  return formatMoney(value, currency, 2);
}

type ParsedCsv = {
  transactions: Transaction[];
  notes: string[];
};

function normalizeHeader(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function findColumn(fields: string[], aliases: string[]) {
  const normalizedAliases = aliases.map(normalizeHeader);
  return fields.find((field) => normalizedAliases.includes(normalizeHeader(field)))
    ?? fields.find((field) => normalizedAliases.some((alias) => alias.length > 3 && normalizeHeader(field).includes(alias)));
}

function parseAmount(value: string | undefined) {
  const original = value?.trim() ?? "";
  if (!original) return null;
  const suffix = original.match(/\b(CR|CREDIT|DR|DEBIT)\s*$/i)?.[1]?.toUpperCase();
  const negative = /^\s*\(.*\)\s*$/.test(original) || /^\s*-/.test(original) || /\bDR(?:EBIT)?\s*$/i.test(original);
  let normalized = original
    .replace(/^\s*\((.*)\)\s*$/, "$1")
    .replace(/\b(CR|CREDIT|DR|DEBIT)\s*$/i, "")
    .replace(/[£$€¥\s]/g, "");
  if (normalized.includes(".") || !/,\d{1,2}$/.test(normalized)) {
    normalized = normalized.replace(/,/g, "");
  } else {
    normalized = normalized.replace(",", ".");
  }
  const parsed = Number(normalized);
  if (!Number.isFinite(parsed)) return null;
  return {
    value: Math.abs(parsed),
    direction: suffix === "DR" || suffix === "DEBIT" || negative
      ? "outflow" as const
      : suffix === "CR" || suffix === "CREDIT"
        ? "inflow" as const
        : parsed < 0
          ? "outflow" as const
          : "inflow" as const,
  };
}

function parseNumericAttribute(value: string | undefined) {
  const parsed = parseAmount(value);
  if (!parsed) return undefined;
  const original = value?.trim() ?? "";
  return /^\s*-/.test(original) || /^\s*\(.*\)\s*$/.test(original) ? -parsed.value : parsed.value;
}

function inferDateColumn(fields: string[], rows: Record<string, string>[]) {
  return fields.find((field) => {
    const values = rows.slice(0, 50).map((row) => row[field]?.trim()).filter((value) => value && !/^\d+$/.test(value));
    return values.length > 0 && values.filter((value) => Number.isFinite(Date.parse(value))).length / values.length >= 0.8;
  });
}

function inferAmountColumn(fields: string[], rows: Record<string, string>[], excluded: string[]) {
  const candidates = fields
    .filter((field) => !excluded.includes(field))
    .map((field) => {
      const values = rows.slice(0, 50).map((row) => row[field]?.trim()).filter(Boolean);
      const numericRatio = values.length
        ? values.filter((value) => parseAmount(value) !== null).length / values.length
        : 0;
      const header = normalizeHeader(field);
      const preferred = /amount|value|total|sum|paid|payment|balance/.test(header);
      const identifier = /^(id|number|accountnumber|reference|ref|code)$/.test(header);
      return { field, score: numericRatio + (preferred ? 0.25 : 0) - (identifier ? 0.5 : 0) };
    })
    .filter((candidate) => candidate.score >= 0.75)
    .sort((left, right) => right.score - left.score);
  return candidates[0]?.field;
}

function parseCsv(text: string): Promise<ParsedCsv> {
  return new Promise((resolve, reject) => {
    Papa.parse<Record<string, string>>(text, {
      header: true,
      skipEmptyLines: "greedy",
      transformHeader: (header) => header.trim(),
      complete: (result) => {
        const headers = result.meta.fields ?? [];
        const rows = result.data;
        if (new Set(headers.map(normalizeHeader)).size !== headers.length) {
          reject(new Error("The CSV contains duplicate column names."));
          return;
        }
        if (result.errors.length) {
          reject(new Error("The CSV could not be parsed. Check its delimiter and row formatting."));
          return;
        }
        if (rows.length > 100_000) {
          reject(new Error("The CSV exceeds the 100,000-row preview limit."));
          return;
        }
        if (!rows.length) {
          reject(new Error("No usable transaction rows were found."));
          return;
        }
        const dateField = findColumn(headers, ["occurred_at", "date", "transaction date", "posting date", "booking date", "value date", "timestamp"])
          ?? inferDateColumn(headers, rows);
        const namedAmountField = findColumn(headers, ["amount", "transaction amount", "value", "net amount", "total", "transaction value"]);
        const amountField = namedAmountField
          ?? inferAmountColumn(headers, rows, dateField ? [dateField] : []);
        const debitField = findColumn(headers, ["debit", "withdrawal", "withdrawals", "money out", "paid out"]);
        const creditField = findColumn(headers, ["credit", "deposit", "deposits", "money in", "paid in"]);
        if (!amountField && !debitField && !creditField) {
          reject(new Error("Could not identify transaction amounts. Include an Amount column, signed values, or separate Debit and Credit columns."));
          return;
        }

        const accountField = findColumn(headers, ["account", "account name", "account number", "account id"]);
        const currencyField = findColumn(headers, ["currency", "currency code", "ccy"]);
        const directionField = findColumn(headers, ["direction", "transaction type", "type", "dr/cr", "credit/debit"]);
        const categoryField = findColumn(headers, ["category", "transaction category"]);
        const referenceField = findColumn(headers, ["transaction id", "reference", "external ref"]);
        const invoiceField = findColumn(headers, ["invoice", "invoice id", "invoice number", "invoice no", "invoice reference"]);
        const productField = findColumn(headers, ["product code", "sku", "stock code", "item code"]);
        const quantityField = findColumn(headers, ["quantity", "qty", "units"]);
        const unitPriceField = findColumn(headers, ["unit price", "price each", "price per unit"]);
        const countryField = findColumn(headers, ["country", "country/region", "region"]);
        const lineTotalField = findColumn(headers, ["line total", "line value", "extended amount"]);
        const returnField = findColumn(headers, ["is return", "return flag", "returned"]);
        const invoiceMonthField = findColumn(headers, ["invoice month", "transaction month"]);
        const weekdayField = findColumn(headers, ["invoice weekday", "weekday", "day of week"]);
        const invoiceHourField = findColumn(headers, ["invoice hour", "hour of day", "transaction hour"]);
        const namedDescriptionField = findColumn(headers, ["description", "transaction description", "details", "merchant", "payee", "narrative", "memo", "reference"]);
        const reservedFields = new Set([
          dateField, amountField, debitField, creditField, accountField, currencyField,
          directionField, categoryField, referenceField,
          invoiceField, productField, quantityField, unitPriceField, countryField,
          lineTotalField, returnField, invoiceMonthField, weekdayField, invoiceHourField,
        ].filter((field): field is string => Boolean(field)));
        const descriptionField = namedDescriptionField ?? headers.find((field) => {
          if (reservedFields.has(field)) return false;
          const values = rows.slice(0, 50).map((row) => row[field]?.trim()).filter(Boolean);
          return values.length > 0 && values.filter((value) => parseAmount(value) === null && !Number.isFinite(Date.parse(value))).length / values.length >= 0.5;
        });
        const notes: string[] = [];
        if (!namedAmountField && amountField) notes.push(`Amount values were inferred from “${amountField}”; verify the selected values.`);
        if (!dateField) notes.push("No date column found; imported rows will show “Not provided” and won’t appear in the timeline.");
        if (!accountField) notes.push("No account column found; rows use “Imported account”.");
        if (!currencyField) notes.push("No currency column found; currency is marked unknown and amounts are not converted.");
        if (amountField && !directionField && !debitField && !creditField
          && rows.some((row) => parseAmount(row[amountField])?.direction === "inflow")) {
          notes.push("Positive amounts are treated as inflows and negative amounts as outflows; check this matches your file.");
        }

        let skippedRows = 0;
        const transactions = rows.flatMap((row, index) => {
          const amount = amountField ? parseAmount(row[amountField]) : null;
          const debit = debitField ? parseAmount(row[debitField]) : null;
          const credit = creditField ? parseAmount(row[creditField]) : null;
          const value = debitField || creditField
            ? (debit?.value ?? 0) + (credit?.value ?? 0)
            : amount?.value ?? 0;
          if (!Number.isFinite(value) || value <= 0) {
            skippedRows += 1;
            return [];
          }
          const directionValue = directionField ? row[directionField]?.trim().toLowerCase() : "";
          const explicitDirection = /debit|withdraw|outflow|expense|paid|purchase/.test(directionValue)
            ? "outflow"
            : /credit|deposit|inflow|income|received|refund/.test(directionValue)
              ? "inflow"
              : null;
          const direction = explicitDirection
            ?? (debit?.value ? "outflow" : credit?.value ? "inflow" : amount?.direction ?? "inflow");
          const rawDate = dateField ? row[dateField]?.trim() ?? "" : "";
          const date = rawDate && Number.isFinite(Date.parse(rawDate)) ? new Date(rawDate).toISOString() : "";
          const rawCurrency = currencyField ? row[currencyField]?.trim().toUpperCase() ?? "" : "";
          const currency = /^[A-Z]{3}$/.test(rawCurrency) ? rawCurrency : "XXX";
          return [{
            occurred_at: date,
            account_name: accountField ? row[accountField]?.trim() || "Imported account" : "Imported account",
            amount: String(value),
            currency,
            direction,
            description: (descriptionField ? row[descriptionField]?.trim() : "") || `Imported transaction ${index + 1}`,
            category: categoryField ? row[categoryField]?.trim() ?? "" : "",
            external_ref: (referenceField ? row[referenceField]?.trim() : "") || String(index + 1),
            invoice_id: invoiceField ? row[invoiceField]?.trim().slice(0, 100) : undefined,
            product_code: productField ? row[productField]?.trim().slice(0, 100) : undefined,
            quantity: quantityField ? parseNumericAttribute(row[quantityField]) : undefined,
            unit_price: unitPriceField ? parseNumericAttribute(row[unitPriceField]) : undefined,
            country: countryField ? row[countryField]?.trim().slice(0, 100) : undefined,
            line_total: lineTotalField ? parseNumericAttribute(row[lineTotalField]) : undefined,
            is_return: returnField
              ? /^(true|1|yes|y|return|returned)$/i.test(row[returnField]?.trim() ?? "")
              : undefined,
            invoice_month: invoiceMonthField ? row[invoiceMonthField]?.trim().slice(0, 20) : undefined,
            invoice_weekday: weekdayField ? row[weekdayField]?.trim().slice(0, 20) : undefined,
            invoice_hour: invoiceHourField ? parseNumericAttribute(row[invoiceHourField]) : undefined,
          }];
        });
        if (!transactions.length) {
          reject(new Error("No rows with usable transaction amounts were found. Check the amount, debit, or credit values."));
          return;
        }
        if (skippedRows) notes.push(`${skippedRows} row${skippedRows === 1 ? " was" : "s were"} skipped because no valid amount was found.`);
        resolve({ transactions, notes });
      },
      error: () => reject(new Error("The selected file could not be read as CSV.")),
    });
  });
}

function App() {
  const [activeView, setActiveView] = useState<View>("overview");
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [trendRun, setTrendRun] = useState<TrendRun | null>(null);
  const [sourceName, setSourceName] = useState("UCI Online Retail sample");
  const [sourceKind, setSourceKind] = useState<"demo" | "local">("demo");
  const [loadingDemo, setLoadingDemo] = useState(true);
  const [apiReady, setApiReady] = useState<boolean | null>(null);
  const [ragReady, setRagReady] = useState(false);
  const [query, setQuery] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch("/health/ready").then((response) => response.ok),
      fetch("/api/v1/demo/uci-online-retail-sample.csv").then(async (response) => {
        if (!response.ok) throw new Error("The demo dataset could not be loaded.");
        return response.text();
      }),
    ])
      .then(async ([ready, text]) => {
      const { transactions: rows } = await parseCsv(text);
        if (!active) return;
        setApiReady(ready);
        setTransactions(rows);
        setTrendRun(null);
      })
      .catch(() => {
        if (active) {
          setApiReady(false);
          setError("Could not connect to the API or load the demo data.");
        }
      })
      .finally(() => {
        if (active) setLoadingDemo(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/v1/public-library/status")
      .then((response) => {
        if (!response.ok) return false;
        return response.json().then((status: PublicLibraryStatus) => status.status === "ready");
      })
      .then((ready) => {
        if (active) setRagReady(ready);
      })
      .catch(() => {
        if (active) setRagReady(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const currencies = new Set(transactions.map((row) => row.currency));
  const currency = currencies.size === 1 && transactions[0]?.currency !== "XXX" ? transactions[0]?.currency ?? null : null;
  const mixedCurrency = currencies.size > 1;
  const unknownCurrency = transactions.some((row) => row.currency === "XXX");
  const totals = useMemo(() => {
    return transactions.reduce(
      (sum, row) => {
        const amount = Number(row.amount);
        if (!Number.isFinite(amount) || (currency && row.currency !== currency)) return sum;
        if (row.direction === "inflow") sum.inflow += amount;
        else sum.outflow += amount;
        return sum;
      },
      { inflow: 0, outflow: 0 },
    );
  }, [currency, transactions]);

  const chartData = useMemo(() => {
    if (new Set(transactions.map((row) => row.currency)).size > 1 || transactions.some((row) => row.currency === "XXX")) return [];
    const months = new Map<string, { month: string; inflow: number; outflow: number }>();
    transactions.forEach((row) => {
      const date = new Date(row.occurred_at);
      if (Number.isNaN(date.valueOf())) return;
      const key = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
      const item = months.get(key) ?? {
        month: date.toLocaleString("en-GB", { month: "short", timeZone: "UTC" }),
        inflow: 0,
        outflow: 0,
      };
      const amount = Number(row.amount);
      if (!Number.isFinite(amount)) return;
      if (row.direction === "inflow") item.inflow += amount;
      else item.outflow += amount;
      months.set(key, item);
    });
    return Array.from(months.values()).slice(-8);
  }, [transactions]);

  const filteredTransactions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return transactions;
    return transactions.filter((row) =>
      [row.description, row.category, row.account_name, row.direction]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [query, transactions]);

  const datasetContext = useMemo<DatasetContext>(() => {
    const currencyTotals = new Map<string, DatasetContext["currencies"][number]>();
    const monthlyTotals = new Map<string, DatasetContext["monthly"][number]>();
    const categoryTotals = new Map<string, DatasetContext["categories"][number]>();
    let undatedCount = 0;
    for (const row of transactions) {
      const amount = Number(row.amount);
      if (!Number.isFinite(amount)) continue;
      const currencyEntry = currencyTotals.get(row.currency) ?? {
        currency: row.currency, inflow: 0, outflow: 0, transactions: 0,
      };
      currencyEntry[row.direction] += amount;
      currencyEntry.transactions += 1;
      currencyTotals.set(row.currency, currencyEntry);

      const date = row.occurred_at ? new Date(row.occurred_at) : null;
      if (!date || Number.isNaN(date.valueOf())) {
        undatedCount += 1;
      } else {
        const month = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
        const monthlyKey = `${row.currency}:${month}`;
        const monthlyEntry = monthlyTotals.get(monthlyKey) ?? {
          month, currency: row.currency, inflow: 0, outflow: 0,
        };
        monthlyEntry[row.direction] += amount;
        monthlyTotals.set(monthlyKey, monthlyEntry);
      }

      const category = row.category.trim().slice(0, 80) || "Uncategorized";
      const categoryKey = `${row.currency}:${category}`;
      const categoryEntry = categoryTotals.get(categoryKey) ?? {
        category, currency: row.currency, inflow: 0, outflow: 0, transactions: 0,
      };
      categoryEntry[row.direction] += amount;
      categoryEntry.transactions += 1;
      categoryTotals.set(categoryKey, categoryEntry);
    }
    return {
      source_kind: sourceKind,
      source_name: sourceName,
      transaction_count: transactions.length,
      undated_count: undatedCount,
      currencies: Array.from(currencyTotals.values()).slice(0, 10),
      monthly: Array.from(monthlyTotals.values())
        .sort((left, right) => left.month.localeCompare(right.month) || left.currency.localeCompare(right.currency))
        .slice(-120),
      categories: Array.from(currencyTotals.keys()).slice(0, 10).flatMap((currencyCode) =>
        Array.from(categoryTotals.values())
          .filter((category) => category.currency === currencyCode)
          .sort((left, right) => right.outflow - left.outflow)
          .slice(0, 5),
      ),
    };
  }, [sourceKind, sourceName, transactions]);

  const { modelSeries, modelInterval } = useMemo(() => {
    if (currencies.size !== 1 || unknownCurrency) {
      return { modelSeries: [], modelInterval: "day" as const };
    }
    const monthly = new Map<string, number>();
    const daily = new Map<string, number>();
    for (const row of transactions) {
      const date = new Date(row.occurred_at);
      const amount = Number(row.amount);
      if (!row.occurred_at || Number.isNaN(date.valueOf()) || !Number.isFinite(amount)) continue;
      const month = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}`;
      const day = `${month}-${String(date.getUTCDate()).padStart(2, "0")}`;
      const netAmount = row.direction === "inflow" ? amount : -amount;
      monthly.set(month, (monthly.get(month) ?? 0) + netAmount);
      daily.set(day, (daily.get(day) ?? 0) + netAmount);
    }
    const interval = monthly.size >= 4 ? "month" as const : "day" as const;
    const buckets = interval === "month" ? monthly : daily;
    const keys = Array.from(buckets.keys()).sort();
    const filledBuckets = new Map<string, number>();
    if (keys.length) {
      const start = interval === "month"
        ? new Date(`${keys[0]}-01T00:00:00Z`)
        : new Date(`${keys[0]}T00:00:00Z`);
      const end = interval === "month"
        ? new Date(`${keys[keys.length - 1]}-01T00:00:00Z`)
        : new Date(`${keys[keys.length - 1]}T00:00:00Z`);
      while (start <= end) {
        const key = interval === "month"
          ? start.toISOString().slice(0, 7)
          : start.toISOString().slice(0, 10);
        filledBuckets.set(key, buckets.get(key) ?? 0);
        if (interval === "month") start.setUTCMonth(start.getUTCMonth() + 1);
        else start.setUTCDate(start.getUTCDate() + 1);
      }
    }
    return {
      modelInterval: interval,
      modelSeries: Array.from(filledBuckets, ([month, net]) => ({
        month,
        net,
        time: interval === "day"
          ? Date.parse(`${month}T00:00:00Z`) / 86_400_000
          : Number(month.slice(0, 4)) * 12 + Number(month.slice(5, 7)) - 1,
      })).sort((left, right) => left.month.localeCompare(right.month)),
    };
  }, [currencies, transactions, unknownCurrency]);

  async function loadSample() {
    setError("");
    setLoadingDemo(true);
    try {
      const response = await fetch("/api/v1/demo/uci-online-retail-sample.csv");
      if (!response.ok) throw new Error("The demo dataset could not be loaded.");
      const { transactions: rows } = await parseCsv(await response.text());
      setTransactions(rows);
      setTrendRun(null);
      setSourceName("UCI Online Retail sample");
      setSourceKind("demo");
      setNotice("The attributed UCI sample is loaded for preview.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The sample could not be loaded.");
    } finally {
      setLoadingDemo(false);
    }
  }

  async function handleFile(file?: File) {
    if (!file) return;
    setError("");
    setNotice("");
    if (!file.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a CSV file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("The CSV exceeds the 10 MiB preview limit.");
      return;
    }
    try {
      const { transactions: rows, notes } = await parseCsv(await file.text());
      setTransactions(rows);
      setTrendRun(null);
      setSourceName(file.name);
      setSourceKind("local");
      setActiveView("transactions");
      const importNotes = notes.length ? ` Import notes: ${notes.join(" ")}` : "";
      setNotice(`${rows.length.toLocaleString()} rows loaded in this browser for preview only.${importNotes}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The selected file could not be read.");
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Activity size={19} strokeWidth={2.6} /></div>
          <div>
            <div className="brand-name">finsight<span>ai</span></div>
            <div className="brand-caption">FINANCIAL INTELLIGENCE</div>
          </div>
        </div>

        <div className="workspace-picker">
          <div className="workspace-avatar">D</div>
          <div className="workspace-copy">
            <span>Workspace</span>
            <strong>Demo company</strong>
          </div>
          <ChevronDown size={15} />
        </div>

        <div className="nav-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navigation.map(({ id, label, icon: Icon }) => (
            <button
              className={`nav-item ${activeView === id ? "active" : ""}`}
              key={id}
              onClick={() => setActiveView(id)}
              type="button"
            >
              <Icon size={17} strokeWidth={1.8} />
              <span>{label}</span>
              {id === "assistant" && <span className="nav-badge">BETA</span>}
            </button>
          ))}
        </nav>

        <div className="nav-label model-label">INTELLIGENCE</div>
        <button
          className={`nav-item ${activeView === "models" ? "active" : ""}`}
          onClick={() => setActiveView("models")}
          type="button"
        >
          <Sparkles size={17} strokeWidth={1.8} />
          <span>Model lab</span>
        </button>

        <div className="sidebar-bottom">
          <div className="api-status">
            <span className={`status-dot ${apiReady ? "online" : ""}`} />
            <div>
              <strong>{apiReady ? "API connected" : apiReady === null ? "Connecting…" : "API unavailable"}</strong>
              <span>Local development</span>
            </div>
            {apiReady === null && <LoaderCircle className="spin" size={14} />}
          </div>
          <button className="help-button" type="button" onClick={() => setActiveView("documents")}>
            <CircleHelp size={17} />
            <span>Help & documentation</span>
          </button>
          <div className="user-row">
            <div className="user-avatar">FS</div>
            <div className="user-copy"><strong>Demo session</strong><span>Preview mode</span></div>
            <ChevronDown size={15} />
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{viewTitles[activeView]}</strong></div>
          <div className="topbar-actions">
            <div className={`connection-pill ${apiReady ? "connected" : ""}`}>
              <span className="status-dot" />{apiReady ? "All systems normal" : "Demo preview"}
            </div>
            <button className="icon-button" aria-label="Notifications" type="button"><Bell size={18} /></button>
            <div className="top-avatar">FS</div>
          </div>
        </header>

        <div className="page-content">
          {error && (
            <div className="alert alert-error" role="alert">
              <X size={16} /><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")} type="button"><X size={15} /></button>
            </div>
          )}
          {notice && (
            <div className="alert alert-success" role="status">
              <Check size={16} /><span>{notice}</span><button aria-label="Dismiss notice" onClick={() => setNotice("")} type="button"><X size={15} /></button>
            </div>
          )}
          {activeView === "overview" && (
            <Overview
              chartData={chartData}
              currency={currency}
              loading={loadingDemo}
              mixedCurrency={mixedCurrency}
              unknownCurrency={unknownCurrency}
              onChooseFile={() => fileInput.current?.click()}
              onView={setActiveView}
              ragReady={ragReady}
              sourceKind={sourceKind}
              sourceName={sourceName}
              today={today}
              totals={totals}
              transactionCount={transactions.length}
            />
          )}
          {activeView === "transactions" && (
            <TransactionsView
              filteredTransactions={filteredTransactions}
              onQuery={setQuery}
              onChooseFile={() => fileInput.current?.click()}
              onResetSample={() => void loadSample()}
              query={query}
              sourceKind={sourceKind}
              sourceName={sourceName}
              transactions={transactions}
            />
          )}
          {activeView === "analysis" && (
            <AnalysisView
              categories={datasetContext.categories}
              chartData={chartData}
              currency={currency}
              mixedCurrency={mixedCurrency}
              sourceKind={sourceKind}
              sourceName={sourceName}
              transactions={transactions}
              transactionCount={transactions.length}
              undatedCount={datasetContext.undated_count}
              unknownCurrency={unknownCurrency}
              totals={totals}
            />
          )}
          {activeView === "forecast" && (
            <ForecastView
              modelCurrency={currency ?? "GBP"}
              onChooseFile={() => fileInput.current?.click()}
              onView={setActiveView}
              run={trendRun}
              sourceKind={sourceKind}
              sourceName={sourceName}
            />
          )}
          {activeView === "documents" && <DocumentsView />}
          {activeView === "assistant" && <AssistantView dataset={datasetContext} />}
          {activeView === "models" && (
            <ModelsView
              modelSeries={modelSeries}
              modelInterval={modelInterval}
              onView={setActiveView}
              onTrain={setTrendRun}
              run={trendRun}
              modelCurrency={currency ?? "GBP"}
              sourceKind={sourceKind}
              sourceName={sourceName}
            />
          )}
          <input
            ref={fileInput}
            accept=".csv,text/csv"
            className="visually-hidden"
            onChange={(event) => void handleFile(event.target.files?.[0])}
            type="file"
          />
        </div>
      </main>
    </div>
  );
}

type OverviewProps = {
  chartData: { month: string; inflow: number; outflow: number }[];
  currency: string | null;
  loading: boolean;
  mixedCurrency: boolean;
  unknownCurrency: boolean;
  onChooseFile: () => void;
  onView: (view: View) => void;
  ragReady: boolean;
  sourceKind: "demo" | "local";
  sourceName: string;
  today: string;
  totals: { inflow: number; outflow: number };
  transactionCount: number;
};

function Overview(props: OverviewProps) {
  const {
    chartData, currency, loading, mixedCurrency, unknownCurrency, onChooseFile, onView, ragReady,
    sourceKind, sourceName, today, totals, transactionCount,
  } = props;
  const net = totals.inflow - totals.outflow;

  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-line" />{today.toUpperCase()}</div>
          <h1>Good afternoon</h1>
          <p>Here’s what’s happening with your financial data.</p>
        </div>
        <button className="button button-primary" onClick={onChooseFile} type="button">
          <Upload size={16} /> Upload transactions
        </button>
      </div>

      <div className="source-banner">
        <div className="banner-icon"><Database size={18} /></div>
        <div className="banner-copy">
          <strong>{sourceKind === "demo" ? "You’re viewing a real-data demo" : "Local CSV preview"}</strong>
          <span>
            {sourceKind === "demo"
              ? "UCI Online Retail · UK sales and returns, 2010–2011. This is not bank or cash-flow data."
              : `${sourceName} · visible only in this browser; it has not been saved or uploaded.`}
          </span>
        </div>
        <span className="banner-tag">{sourceKind === "demo" ? "DEMO DATA" : "LOCAL ONLY"}</span>
      </div>

      {sourceKind === "demo" && (
        <div className="source-note">
          <ShieldCheck size={14} />
          <span>Source: <a href="https://archive.ics.uci.edu/dataset/352/online+retail" target="_blank" rel="noreferrer">UCI Machine Learning Repository</a> · CC BY 4.0 · DOI 10.24432/C5BW33</span>
        </div>
      )}

      <section className="metric-grid" aria-label="Transaction summary">
        <MetricCard
          label={sourceKind === "demo" ? "Sales proxy" : "Total inflows"}
          value={loading || !transactionCount ? "—" : mixedCurrency ? "Mixed" : currency ? formatMoney(totals.inflow, currency) : "—"}
          change={mixedCurrency ? "Multiple currencies; not combined" : unknownCurrency ? "Currency missing; total withheld" : "Based on loaded rows"}
          icon={ArrowDownLeft}
          tone="green"
        />
        <MetricCard
          label={sourceKind === "demo" ? "Returns proxy" : "Total outflows"}
          value={loading || !transactionCount ? "—" : mixedCurrency ? "Mixed" : currency ? formatMoney(totals.outflow, currency) : "—"}
          change={mixedCurrency ? "Multiple currencies; not combined" : unknownCurrency ? "Currency missing; total withheld" : "Based on loaded rows"}
          icon={ArrowUpRight}
          tone="orange"
        />
        <MetricCard
          label={sourceKind === "demo" ? "Net sales proxy" : "Net movement"}
          value={loading || !transactionCount ? "—" : mixedCurrency ? "Mixed" : currency ? formatMoney(net, currency) : "—"}
          change={mixedCurrency ? "Multiple currencies; not combined" : unknownCurrency ? "Currency missing; total withheld" : sourceKind === "demo" ? "Sales less returns; not cash" : "Not a cash balance"}
          icon={Wallet}
          tone="blue"
        />
        <MetricCard
          label="Transactions"
          value={loading ? "—" : transactionCount.toLocaleString()}
          change={sourceKind === "demo" ? "Sample source rows" : "Local preview rows"}
          icon={Activity}
          tone="purple"
        />
      </section>

      <div className="overview-grid">
        <section className="panel flow-panel">
          <div className="panel-heading">
            <div><h2>Transaction activity</h2><p>Monthly totals · {sourceName}</p></div>
            <button className="text-button" onClick={() => onView("transactions")} type="button">View transactions <ArrowRight size={14} /></button>
          </div>
          {chartData.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 12, right: 6, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#278b69" stopOpacity={0.19} />
                      <stop offset="95%" stopColor="#278b69" stopOpacity={0.01} />
                    </linearGradient>
                    <linearGradient id="returnsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#d99555" stopOpacity={0.17} />
                      <stop offset="95%" stopColor="#d99555" stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#edf0ec" vertical={false} />
                  <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 11 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 11 }} tickFormatter={(value: number) => `£${Math.round(value / 1000)}k`} width={42} />
                  <Tooltip
                    contentStyle={{ border: "1px solid #e8ece8", borderRadius: 10, boxShadow: "0 8px 24px #17251d12" }}
                    formatter={(value) => formatMoney(Number(value), currency ?? "GBP")}
                  />
                  <Area type="monotone" dataKey="inflow" name="Sales proxy" stroke="#278b69" strokeWidth={2.2} fill="url(#salesFill)" />
                  <Area type="monotone" dataKey="outflow" name="Returns proxy" stroke="#d99555" strokeWidth={2} fill="url(#returnsFill)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-chart"><Activity size={21} /><span>{loading ? "Loading source data…" : mixedCurrency ? "Mixed currencies; monthly totals are not combined." : unknownCurrency ? "Currency is unknown; chart totals are not shown." : "No date-valid rows to chart."}</span></div>
          )}
          <div className="chart-legend">
            <span><i className="legend-dot green-dot" />Sales proxy</span>
            <span><i className="legend-dot orange-dot" />Returns proxy</span>
            <span className="chart-footnote">Source records only · not a forecast</span>
          </div>
        </section>

        <section className="panel readiness-panel">
          <div className="panel-heading"><div><h2>Platform readiness</h2><p>What’s live in this build</p></div><span className="live-tag"><i /> PREVIEW</span></div>
          <ReadinessItem icon={Database} title="CSV preview" detail="Local file parsing" state="ready" />
          <ReadinessItem icon={LockKeyhole} title="Secure sign-in" detail="Identity provider not configured" state="pending" />
          <ReadinessItem
            icon={FileText}
            title="Public source search"
            detail={ragReady ? "SBA + IRS text indexed" : "Public sources need indexing"}
            state={ragReady ? "ready" : "pending"}
          />
          <ReadinessItem icon={Sparkles} title="Cash-flow model" detail="No model trained or evaluated" state="pending" />
          <button className="readiness-link" onClick={() => onView("models")} type="button">See what’s needed <ArrowRight size={14} /></button>
        </section>
      </div>

      <section className="bottom-grid">
        <div className="panel onboarding-panel">
          <div className="onboarding-art"><div className="art-circle"><BarChart3 size={24} /></div><div className="art-line" /><div className="art-dot" /></div>
          <div className="onboarding-copy">
            <div className="eyebrow">YOUR NEXT STEP</div>
            <h2>Connect your business data</h2>
            <p>Preview a CSV in your browser. To persist financial data, secure sign-in and organization setup must be configured first.</p>
            <button className="button button-secondary" onClick={onChooseFile} type="button">Choose a CSV <ArrowRight size={15} /></button>
          </div>
        </div>
        <div className="panel insight-panel">
          <div className="insight-icon"><CircleHelp size={17} /></div>
          <div><span className="eyebrow">A NOTE ON THIS DEMO</span><h2>Sales are not cash flow</h2><p>Retail invoice data doesn’t include settlement dates, expenses, or balances. It can test imports—not prove forecasts.</p><button className="subtle-link" onClick={() => onView("forecast")} type="button">Why no forecast yet? <ArrowRight size={13} /></button></div>
        </div>
      </section>
      <footer className="page-footer"><span>FinSight AI · Development preview</span><span>Numbers show source records; no financial advice or model predictions.</span></footer>
    </>
  );
}

function MetricCard({
  label, value, change, icon: Icon, tone,
}: {
  label: string;
  value: string;
  change: string;
  icon: typeof Activity;
  tone: string;
}) {
  return (
    <article className="metric-card">
      <div className="metric-top"><span>{label}</span><span className={`metric-icon ${tone}`}><Icon size={17} strokeWidth={2} /></span></div>
      <strong className="metric-value">{value}</strong>
      <span className="metric-caption"><Clock3 size={12} />{change}</span>
    </article>
  );
}

function ReadinessItem({
  icon: Icon, title, detail, state,
}: {
  icon: typeof Activity;
  title: string;
  detail: string;
  state: "ready" | "pending";
}) {
  return (
    <div className="readiness-item">
      <div className="readiness-icon"><Icon size={16} /></div>
      <div className="readiness-copy"><strong>{title}</strong><span>{detail}</span></div>
      <span className={`readiness-state ${state}`}>{state === "ready" ? "Ready" : "Pending"}</span>
    </div>
  );
}

function TransactionsView({
  filteredTransactions, onQuery, onChooseFile, onResetSample, query, sourceKind, sourceName, transactions,
}: {
  filteredTransactions: Transaction[];
  onQuery: (value: string) => void;
  onChooseFile: () => void;
  onResetSample: () => void;
  query: string;
  sourceKind: "demo" | "local";
  sourceName: string;
  transactions: Transaction[];
}) {
  return (
    <>
      <div className="page-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" />FINANCIAL DATA</div><h1>Transactions</h1><p>Review the rows in your current dataset.</p></div>
        <div className="heading-actions">
          {sourceKind === "local" && <button className="button button-secondary" onClick={onResetSample} type="button">Reset demo data</button>}
          <button className="button button-primary" onClick={onChooseFile} type="button"><Upload size={16} /> Preview a CSV</button>
        </div>
      </div>
      <div className="source-banner compact-banner">
        <div className="banner-icon"><Database size={18} /></div>
        <div className="banner-copy"><strong>{sourceName}</strong><span>{sourceKind === "demo" ? "Public source sample · preview mode" : "Browser-only preview · not persisted"}</span></div>
        <span className="banner-tag">{transactions.length.toLocaleString()} ROWS</span>
      </div>
      <section className="panel table-panel">
        <div className="table-toolbar">
          <div><h2>All transactions</h2><p>{filteredTransactions.length.toLocaleString()} of {transactions.length.toLocaleString()} rows</p></div>
          <label className="search-field"><Search size={16} /><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder="Search transactions" /></label>
        </div>
        <div className="table-scroll">
          <table>
            <thead><tr><th>Transaction</th><th>Date</th><th>Category</th><th>Type</th><th className="amount-cell">Amount</th></tr></thead>
            <tbody>
              {filteredTransactions.slice(0, 100).map((row, index) => (
                <tr key={`${row.external_ref}-${index}`}>
                  <td><div className="transaction-name"><span className={`transaction-type-icon ${row.direction}`}><ArrowDownRight size={14} /></span><span><strong>{row.description || "Uncategorized transaction"}</strong><small>{row.account_name}</small></span></div></td>
                  <td>{row.occurred_at
                    ? new Date(row.occurred_at).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" })
                    : "Not provided"}</td>
                  <td><span className="category-chip">{row.category || "Uncategorized"}</span></td>
                  <td><span className={`direction-label ${row.direction}`}>{row.direction}</span></td>
                  <td className={`amount-cell ${row.direction}`}>{row.direction === "outflow" ? "−" : "+"}{formatTransactionAmount(Number(row.amount), row.currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filteredTransactions.length && <div className="table-empty">No rows match this search.</div>}
          {filteredTransactions.length > 100 && <div className="table-note">Showing the first 100 rows. Refine your search to narrow the preview.</div>}
        </div>
        <div className="table-disclaimer"><ShieldCheck size={14} />Preview only. This file stays in your browser and is not sent to the API.</div>
      </section>
    </>
  );
}

function AnalysisView({
  categories, chartData, currency, mixedCurrency, sourceKind, sourceName, transactions, transactionCount,
  undatedCount, unknownCurrency, totals,
}: {
  categories: DatasetContext["categories"];
  chartData: { month: string; inflow: number; outflow: number }[];
  currency: string | null;
  mixedCurrency: boolean;
  sourceKind: "demo" | "local";
  sourceName: string;
  transactions: Transaction[];
  transactionCount: number;
  undatedCount: number;
  unknownCurrency: boolean;
  totals: { inflow: number; outflow: number };
}) {
  const invoiceIds = new Set(transactions.map((row) => row.invoice_id).filter((value): value is string => Boolean(value)));
  const products = new Set(transactions.map((row) => row.product_code).filter((value): value is string => Boolean(value)));
  const countries = new Set(transactions.map((row) => row.country).filter((value): value is string => Boolean(value)));
  const quantifiedRows = transactions.filter((row) => Number.isFinite(row.quantity));
  const quantitySum = quantifiedRows.reduce((sum, row) => sum + (row.quantity ?? 0), 0);
  const summarizeDimension = (keyOf: (row: Transaction) => string) => {
    const grouped = new Map<string, { label: string; currency: string; amount: number; count: number }>();
    transactions.forEach((row) => {
      const label = keyOf(row);
      if (!label) return;
      const key = `${row.currency}:${label}`;
      const summary = grouped.get(key) ?? { label, currency: row.currency, amount: 0, count: 0 };
      summary.amount += Number(row.amount) || 0;
      summary.count += 1;
      grouped.set(key, summary);
    });
    const byCurrency = new Map<
      string,
      { label: string; currency: string; amount: number; count: number }[]
    >();
    for (const summary of grouped.values()) {
      const current = byCurrency.get(summary.currency) ?? [];
      current.push(summary);
      byCurrency.set(summary.currency, current);
    }
    return Array.from(byCurrency.entries()).flatMap(([currencyCode, items]) => {
      const ordered = items.sort((left, right) => right.amount - left.amount);
      return ordered.slice(0, 5).map((item) => ({
        ...item,
        currencyPeak: ordered[0].amount,
        currencyCode,
      }));
    });
  };
  const topCountries = summarizeDimension((row) => row.country ?? "");
  const topProducts = summarizeDimension((row) => row.product_code || row.description);
  const currenciesWithPrices = transactions.filter((row) => Number.isFinite(row.unit_price));
  const selectedPriceRows = currency
    ? currenciesWithPrices.filter((row) => row.currency === currency)
    : [];
  const averageUnitPrice = selectedPriceRows.length
    ? selectedPriceRows.reduce((sum, row) => sum + (row.unit_price ?? 0), 0) / selectedPriceRows.length
    : null;
  const categoriesByCurrency = new Map<string, typeof categories>();
  for (const category of categories) {
    if (category.outflow <= 0) continue;
    const items = categoriesByCurrency.get(category.currency) ?? [];
    items.push(category);
    categoriesByCurrency.set(category.currency, items);
  }
  const biggestCategories = Array.from(categoriesByCurrency.entries()).flatMap(([currencyCode, items]) =>
    items.sort((left, right) => right.outflow - left.outflow)
      .slice(0, 4)
      .map((item) => ({ ...item, currencyPeak: items[0].outflow, currencyCode })),
  );
  const availableAttributes: [string, number][] = [
    ["invoice IDs", invoiceIds.size],
    ["product codes", products.size],
    ["quantities", quantifiedRows.length],
    ["unit prices", currenciesWithPrices.length],
    ["countries / regions", countries.size],
  ];
  const analysisPeriods = new Map<string, { period: string; inflow: number; outflow: number }>();
  const weekdayPeriods = new Map<string, { weekday: string; inflow: number; outflow: number }>();
  const hourlyCounts = new Map<number, number>();
  const weekdayOrder = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  for (const row of transactions) {
    const date = row.occurred_at ? new Date(row.occurred_at) : null;
    if (!date || Number.isNaN(date.valueOf())) continue;
    const amount = Number(row.amount);
    if (!Number.isFinite(amount)) continue;
    const period = row.invoice_month || date.toISOString().slice(0, 7);
    const periodEntry = analysisPeriods.get(period) ?? { period, inflow: 0, outflow: 0 };
    periodEntry[row.direction] += amount;
    analysisPeriods.set(period, periodEntry);

    const weekday = row.invoice_weekday
      || weekdayOrder[(date.getUTCDay() + 6) % weekdayOrder.length];
    if (weekdayOrder.includes(weekday)) {
      const weekdayEntry = weekdayPeriods.get(weekday) ?? { weekday, inflow: 0, outflow: 0 };
      weekdayEntry[row.direction] += amount;
      weekdayPeriods.set(weekday, weekdayEntry);
    }

    const hour = row.invoice_hour ?? date.getUTCHours();
    if (Number.isInteger(hour) && hour >= 0 && hour <= 23) {
      hourlyCounts.set(hour, (hourlyCounts.get(hour) ?? 0) + 1);
    }
  }
  const monthlyNetData = Array.from(analysisPeriods.values())
    .sort((left, right) => left.period.localeCompare(right.period))
    .map((item) => ({ ...item, net: item.inflow - item.outflow }));
  const weekdayData = weekdayOrder
    .map((weekday) => weekdayPeriods.get(weekday) ?? { weekday, inflow: 0, outflow: 0 });
  const hourlyData = Array.from({ length: 24 }, (_, hour) => ({
    hour: `${String(hour).padStart(2, "0")}:00`,
    transactions: hourlyCounts.get(hour) ?? 0,
  }));
  const returnRows = transactions.filter((row) => row.is_return === true).length;
  const net = totals.inflow - totals.outflow;

  return (
    <>
      <div className="page-heading">
        <div><div className="eyebrow"><span className="eyebrow-line" />TRANSACTION INSIGHTS</div><h1>Analysis</h1><p>Explore trends and spending patterns in the current dataset.</p></div>
      </div>
      <div className="source-banner compact-banner">
        <div className="banner-icon"><Database size={18} /></div>
        <div className="banner-copy">
          <strong>{sourceKind === "demo" ? "Analysis of the UCI retail demo" : "Analysis of your local CSV"}</strong>
          <span>{sourceName} · {sourceKind === "local" ? "Processed in this browser" : "Public sample data"}</span>
        </div>
        <span className="banner-tag">{transactionCount.toLocaleString()} ROWS</span>
      </div>
      {sourceKind === "demo" && (
        <section className="analysis-caveat">
          <ShieldCheck size={15} />
          <p>These are historic retail sales and returns, not bank transactions. Use the patterns to explore the app—not as a cash balance or business forecast.</p>
        </section>
      )}
      <section className="metric-grid analysis-metrics" aria-label="Transaction analysis summary">
        <MetricCard label="Inflows" value={mixedCurrency ? "Mixed" : currency ? formatMoney(totals.inflow, currency) : "—"} change="Sum of inflow rows" icon={ArrowDownLeft} tone="green" />
        <MetricCard label="Outflows" value={mixedCurrency ? "Mixed" : currency ? formatMoney(totals.outflow, currency) : "—"} change="Sum of outflow rows" icon={ArrowUpRight} tone="orange" />
        <MetricCard label="Net movement" value={mixedCurrency ? "Mixed" : currency ? formatMoney(net, currency) : "—"} change="Not a cash balance" icon={Wallet} tone="blue" />
        <MetricCard label="Rows without dates" value={undatedCount.toLocaleString()} change="Not included in timeline" icon={Clock3} tone="purple" />
      </section>
      <section className="metric-grid analysis-metrics attribute-metrics" aria-label="Additional transaction attributes">
        <MetricCard label="Distinct invoices" value={invoiceIds.size ? invoiceIds.size.toLocaleString() : "—"} change={invoiceIds.size ? "Invoice identifiers found" : "No invoice column detected"} icon={FileText} tone="green" />
        <MetricCard label="Product / merchant labels" value={products.size ? products.size.toLocaleString() : "—"} change={products.size ? "Distinct product codes" : "Description labels available below"} icon={Database} tone="blue" />
        <MetricCard label="Quantity sum" value={quantifiedRows.length ? new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(quantitySum) : "—"} change={quantifiedRows.length ? `${quantifiedRows.length.toLocaleString()} rows include quantity` : "No quantity column detected"} icon={Activity} tone="purple" />
        <MetricCard label="Return rows" value={returnRows ? returnRows.toLocaleString() : "—"} change={returnRows ? "Explicit return flag" : "No explicit return flag"} icon={ArrowDownRight} tone="orange" />
      </section>
      {averageUnitPrice !== null && currency && (
        <section className="analysis-note-strip">
          <span>Average unit price</span><strong>{formatMoney(averageUnitPrice, currency, 2)}</strong>
          <span>{currenciesWithPrices.length.toLocaleString()} rows include unit-price data.</span>
        </section>
      )}
      <div className="analysis-grid">
        <section className="panel flow-panel analysis-flow-panel">
          <div className="panel-heading"><div><h2>Monthly transaction activity</h2><p>Inflows and outflows · {sourceName}</p></div></div>
          {chartData.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 12, right: 6, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#edf0ec" vertical={false} />
                  <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 11 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 11 }} width={42} />
                  <Tooltip formatter={(value) => formatMoney(Number(value), currency ?? "GBP")} />
                  <Area type="monotone" dataKey="inflow" name="Inflows" stroke="#278b69" strokeWidth={2.2} fill="#278b6920" />
                  <Area type="monotone" dataKey="outflow" name="Outflows" stroke="#d99555" strokeWidth={2} fill="#d9955520" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="empty-chart"><Activity size={21} /><span>{mixedCurrency ? "Monthly amounts are not combined across currencies." : unknownCurrency ? "Currency is unknown; chart totals are not shown." : "No date-valid rows to chart."}</span></div>
          )}
          {mixedCurrency && <div className="inline-notice">Currency totals are kept separate; choose one currency in your source for a combined trend.</div>}
        </section>
        <section className="panel category-analysis">
          <div className="panel-heading"><div><h2>Largest outflow categories</h2><p>Ranked by amount within each currency</p></div></div>
          {biggestCategories.length ? (
            <div className="category-bars">
              {biggestCategories.map((item) => (
                <div className="category-bar-row" key={`${item.currency}-${item.category}`}>
                  <div className="category-bar-label"><span>{item.category}</span><strong>{formatTransactionAmount(item.outflow, item.currencyCode)}</strong></div>
                  <div className="category-bar-track"><span style={{ width: `${item.currencyPeak ? Math.max(4, item.outflow / item.currencyPeak * 100) : 0}%` }} /></div>
                  <small>{item.transactions} rows · {item.currencyCode}</small>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-chart"><span>No categorized outflows found in this dataset.</span></div>
          )}
        </section>
      </div>
      {currency && (
        <div className="analysis-grid additional-analysis-grid">
          <section className="panel category-analysis analysis-chart-panel">
            <div className="panel-heading"><div><h2>Monthly net movement</h2><p>Inflows less outflows · all available months</p></div></div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={monthlyNetData} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#edf0ec" vertical={false} />
                  <XAxis dataKey="period" axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 9 }} dy={8} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 10 }} width={48} />
                  <Tooltip formatter={(value) => formatMoney(Number(value), currency, 2)} />
                  <Line dataKey="net" name="Net movement" stroke="#528a69" strokeWidth={2} dot={{ r: 2 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="panel category-analysis analysis-chart-panel">
            <div className="panel-heading"><div><h2>Activity by weekday</h2><p>Gross inflows and outflows · currency totals kept separate</p></div></div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weekdayData} margin={{ top: 12, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#edf0ec" vertical={false} />
                  <XAxis dataKey="weekday" axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 9 }} dy={8} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 10 }} width={48} />
                  <Tooltip formatter={(value) => formatMoney(Number(value), currency, 2)} />
                  <Bar dataKey="inflow" name="Inflows" fill="#5da47b" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="outflow" name="Outflows" fill="#d99555" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
          <section className="panel category-analysis analysis-chart-panel">
            <div className="panel-heading"><div><h2>Transaction timing</h2><p>Rows by invoice hour · based on source local time when available</p></div></div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hourlyData} margin={{ top: 12, right: 4, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="#edf0ec" vertical={false} />
                  <XAxis dataKey="hour" interval={3} axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 9 }} dy={8} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 10 }} width={36} />
                  <Tooltip />
                  <Bar dataKey="transactions" name="Rows" fill="#8796bf" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        </div>
      )}
      {(topCountries.length > 0 || topProducts.length > 0) && (
        <div className="analysis-grid additional-analysis-grid">
          {topCountries.length > 0 && (
            <section className="panel category-analysis">
              <div className="panel-heading"><div><h2>Transaction amount by country / region</h2><p>Sampled transaction amount · shown separately by currency</p></div></div>
              <div className="category-bars">
                {topCountries.map((item) => (
                  <div className="category-bar-row" key={`${item.currencyCode}-${item.label}`}>
                    <div className="category-bar-label"><span>{item.label}</span><strong>{formatTransactionAmount(item.amount, item.currencyCode)}</strong></div>
                    <div className="category-bar-track"><span style={{ width: `${item.currencyPeak ? Math.max(4, item.amount / item.currencyPeak * 100) : 0}%` }} /></div>
                    <small>{item.count} rows · {item.currencyCode}</small>
                  </div>
                ))}
              </div>
            </section>
          )}
          {topProducts.length > 0 && (
            <section className="panel category-analysis">
              <div className="panel-heading"><div><h2>Top products / descriptions</h2><p>Sampled transaction amount · shown separately by currency</p></div></div>
              <div className="category-bars">
                {topProducts.map((item) => (
                  <div className="category-bar-row" key={`${item.currencyCode}-${item.label}`}>
                    <div className="category-bar-label"><span>{item.label}</span><strong>{formatTransactionAmount(item.amount, item.currencyCode)}</strong></div>
                    <div className="category-bar-track"><span style={{ width: `${item.currencyPeak ? Math.max(4, item.amount / item.currencyPeak * 100) : 0}%` }} /></div>
                    <small>{item.count} rows · {item.currencyCode}</small>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
      <section className="panel analysis-quality">
        <div className="panel-heading"><div><h2>Data quality notes</h2><p>Interpret the analysis with care</p></div></div>
        <div className="quality-note-grid">
          <div><strong>{undatedCount.toLocaleString()}</strong><span>rows missing usable dates</span></div>
          <div><strong>{unknownCurrency ? "Unknown present" : mixedCurrency ? "Multiple" : currency ?? "Unknown"}</strong><span>currency context</span></div>
          <div><strong>{categories.filter((item) => item.category === "Uncategorized").reduce((sum, item) => sum + item.transactions, 0).toLocaleString()}</strong><span>rows without category labels</span></div>
          <div><strong>{countries.size.toLocaleString()}</strong><span>distinct country values</span></div>
          <div><strong>{invoiceIds.size.toLocaleString()}</strong><span>distinct invoice references</span></div>
        </div>
        <p className="attribute-coverage">Available CSV attributes: {availableAttributes.filter(([, count]) => count > 0).map(([label]) => label).join(", ") || "none of invoice, product, quantity, unit price, or country/region"}.</p>
      </section>
    </>
  );
}

function ForecastView({
  modelCurrency, onChooseFile, onView, run, sourceKind, sourceName,
}: {
  modelCurrency: string;
  onChooseFile: () => void;
  onView: (view: View) => void;
  run: TrendRun | null;
  sourceKind: "demo" | "local";
  sourceName: string;
}) {
  const [openingBalance, setOpeningBalance] = useState("");
  const [confirmedCashFlows, setConfirmedCashFlows] = useState(false);
  const balanceValue = openingBalance.trim() ? Number(openingBalance) : Number.NaN;
  const canProjectBalance = sourceKind === "local"
    && Boolean(run)
    && confirmedCashFlows
    && Number.isFinite(balanceValue);
  const projectedBalances = canProjectBalance && run
    ? run.forecasts.reduce<{ month: string; estimate: number; balance: number }[]>((forecast, item) => {
      const previousBalance = forecast[forecast.length - 1]?.balance ?? balanceValue;
      forecast.push({ ...item, balance: previousBalance + item.estimate });
      return forecast;
    }, [])
    : [];
  const intervalLabel = run?.interval === "month" ? "Monthly" : "Daily";

  return (
    <>
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />FORECASTING</div><h1>Cash flow</h1><p>Project receipts, payments, and a balance from a cash-flow CSV.</p></div><span className="pending-pill">{sourceKind === "demo" ? "UPLOAD DATA" : run ? "MODEL READY" : "TRAIN MODEL"}</span></div>
      {sourceKind === "demo" ? (
        <section className="panel blocked-panel">
          <div className="blocked-icon"><BarChart3 size={24} /></div>
          <div className="eyebrow">CASH-FLOW DATA NEEDED</div>
          <h2>Upload dated cash receipts and payments</h2>
          <p>The current UCI demo contains retail invoice lines, not bank movements. Cash flow stays empty until you preview a CSV with dated inflows/outflows and one known currency; retail sales are not treated as cash receipts.</p>
          <div className="requirement-list">
            <div><span className="requirement-number">01</span><span><strong>Use cash movements</strong><small>Include actual receipt/payment amounts, a transaction date, and one currency.</small></span></div>
            <div><span className="requirement-number">02</span><span><strong>Train and compare</strong><small>Model lab evaluates several baselines on a chronological holdout.</small></span></div>
            <div><span className="requirement-number">03</span><span><strong>Project a balance only with evidence</strong><small>Enter a verified opening balance and confirm the rows are cash flows.</small></span></div>
          </div>
          <button className="button button-primary" onClick={onChooseFile} type="button"><Upload size={15} />Upload cash-flow CSV</button>
        </section>
      ) : !run ? (
        <section className="panel blocked-panel">
          <div className="blocked-icon"><BarChart3 size={24} /></div>
          <div className="eyebrow">READY FOR A CASH-FLOW RUN</div>
          <h2>Train a model on the current CSV</h2>
          <p>Model lab compares a last-period baseline, moving average, and linear trend using a chronological holdout. To project a balance, you’ll also need a verified opening balance and confirmation that these rows represent actual cash receipts/payments.</p>
          <button className="button button-secondary" onClick={() => onView("models")} type="button">Open model lab <ArrowRight size={15} /></button>
        </section>
      ) : (
        <>
          <section className="panel model-status-panel">
            <div className="panel-heading"><div><h2>{intervalLabel} transaction-movement estimate</h2><p>{sourceName} · {run.method} selected from {run.scores.length} candidates · {run.holdoutCount} chronological holdout periods</p></div></div>
            <div className="model-facts">
              <div><span>Selected method</span><strong>{run.method}</strong></div>
              <div><span>Selected holdout MAE</span><strong>{formatMoney(run.mae, modelCurrency, 2)}</strong></div>
              <div><span>Holdout RMSE</span><strong>{formatMoney(run.rmse, modelCurrency, 2)}</strong></div>
              <div><span>Symmetric percentage error</span><strong>{run.smape.toFixed(1)}%</strong></div>
            </div>
            <div className="model-score-list">
              {run.scores.map((score) => (
                <div key={score.method} className={score.method === run.method ? "selected" : ""}>
                  <strong>{score.method}</strong><span>MAE {formatMoney(score.mae, modelCurrency, 2)}</span><span>RMSE {formatMoney(score.rmse, modelCurrency, 2)}</span><span>sMAPE {score.smape.toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <div className="model-forecast-grid" aria-live="polite">
              {run.forecasts.map((item) => (
                <div key={item.month}><span>{item.month}</span><strong>{formatMoney(item.estimate, modelCurrency, 2)}</strong><small>{confirmedCashFlows ? "Estimated net cash movement" : "Estimated net transaction movement"}</small></div>
              ))}
            </div>
          </section>
          <section className="panel balance-projection-panel">
              <div className="panel-heading"><div><h2>Optional balance projection</h2><p>Requires your verified starting balance and confirmation of what the CSV represents.</p></div></div>
              <label className="balance-input-label" htmlFor="opening-balance">Verified starting balance ({modelCurrency})</label>
              <input
                className="balance-input"
                id="opening-balance"
                inputMode="decimal"
                onChange={(event) => setOpeningBalance(event.target.value)}
                placeholder="Enter starting balance"
                type="number"
                value={openingBalance}
              />
              <label className="balance-confirmation">
                <input
                  checked={confirmedCashFlows}
                  onChange={(event) => setConfirmedCashFlows(event.target.checked)}
                  type="checkbox"
                />
                <span>I confirm these rows represent actual cash receipts and cash payments in the selected currency. Once confirmed, movement estimates may be used for the optional balance projection.</span>
              </label>
              {projectedBalances.length > 0 ? (
                <div className="model-forecast-grid" aria-live="polite">
                  {projectedBalances.map((item) => (
                    <div key={item.month}><span>{item.month}</span><strong>{formatMoney(item.balance, modelCurrency, 2)}</strong><small>Exploratory projected balance</small></div>
                  ))}
                </div>
              ) : (
                <p className="model-requirement">Enter a finite starting balance and confirm the rows are actual cash receipts/payments to calculate projected balances.</p>
              )}
          </section>
          <section className="panel data-caveat">
            <div className="caveat-mark"><CircleHelp size={16} /></div>
            <div><strong>Review the backtest before relying on projections</strong><p>The model selection is an automatically scored historical holdout, not independent validation. Check whether the holdout represents your business and whether unusual items, seasonality, or planned future transactions could change the result.</p></div>
          </section>
          <button className="button button-secondary forecast-model-link" onClick={() => onView("models")} type="button">Review model lab <ArrowRight size={15} /></button>
        </>
      )}
    </>
  );
}

function DocumentsView() {
  const [libraryStatus, setLibraryStatus] = useState<PublicLibraryStatus | null>(null);
  const [statusMessage, setStatusMessage] = useState("Checking public source index…");
  const [searchText, setSearchText] = useState("");
  const [results, setResults] = useState<PublicSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/v1/public-library/status")
      .then(async (response) => {
        if (response.status === 503) {
          if (active) setStatusMessage("Sources selected; run the local indexing command to enable search.");
          return null;
        }
        if (!response.ok) throw new Error("The public source index is unavailable.");
        return response.json() as Promise<PublicLibraryStatus>;
      })
      .then((status) => {
        if (!active || !status) return;
        setLibraryStatus(status);
        setStatusMessage(`${status.source_count} public sources · ${status.chunk_count.toLocaleString()} passages`);
      })
      .catch(() => {
        if (active) setStatusMessage("Could not check the public source index.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function searchSources(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSearchError("");
    if (!searchText.trim()) {
      setSearchError("Enter a topic to search.");
      return;
    }
    setSearching(true);
    try {
      const params = new URLSearchParams({ query: searchText });
      const response = await fetch(`/api/v1/public-library/search?${params}`);
      if (!response.ok) throw new Error("Source search is unavailable. Check that the library is indexed.");
      const payload = (await response.json()) as { results: PublicSearchResult[] };
      setResults(payload.results);
      if (!payload.results.length) setSearchError("No matching source passages were found.");
    } catch (reason) {
      setResults([]);
      setSearchError(reason instanceof Error ? reason.message : "Source search failed.");
    } finally {
      setSearching(false);
    }
  }

  return (
    <>
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />PUBLIC KNOWLEDGE BASE</div><h1>Documents</h1><p>Search source-linked small-business finance and tax guidance.</p></div></div>
      <section className="panel library-panel">
        <div className="library-heading">
          <div className="library-icon"><Database size={18} /></div>
          <div><h2>Public source library</h2><p>{statusMessage}</p></div>
          <span className={`readiness-state ${libraryStatus ? "ready" : "pending"}`}>{libraryStatus ? "Indexed" : "Setup needed"}</span>
        </div>
        <form className="library-search" onSubmit={(event) => void searchSources(event)}>
          <Search size={17} />
          <input
            disabled={!libraryStatus || searching}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search bookkeeping, cash flow, business taxes…"
            value={searchText}
          />
          <button className="button button-primary" disabled={!libraryStatus || searching} type="submit">
            {searching ? <LoaderCircle className="spin" size={15} /> : <Search size={15} />}
            Search sources
          </button>
        </form>
        {searchError && <p className="search-message" role="status">{searchError}</p>}
        {results.length > 0 && (
          <div className="search-results" aria-live="polite">
            <div className="results-heading">{results.length} cited passage{results.length === 1 ? "" : "s"}</div>
            {results.map((result) => (
              <article className="source-result" key={result.chunk_id}>
                <div className="result-meta">{result.publisher} · {result.edition}{result.section ? ` · ${result.section}` : ""}</div>
                <p>{result.excerpt}</p>
                <a href={result.url} rel="noreferrer" target="_blank">{result.title} <ArrowUpRight size={12} /></a>
              </article>
            ))}
          </div>
        )}
        {libraryStatus ? (
          <div className="source-list">
            <div className="results-heading">Indexed sources</div>
            {libraryStatus.sources.map((source) => (
              <div className="library-source" key={source.source_id}>
                <FileText size={15} />
                <div><a href={source.url} rel="noreferrer" target="_blank">{source.title} <ArrowUpRight size={12} /></a><span>{source.publisher} · {source.edition} · {source.chunk_count} passages</span><small>{source.rights_basis}</small></div>
              </div>
            ))}
          </div>
        ) : (
          <div className="inline-notice"><LockKeyhole size={15} /><span>Local index pending. Ingest only agency-authored page text; linked or third-party content is excluded.</span></div>
        )}
      </section>
      <section className="panel library-disclaimer">
        <ShieldCheck size={15} />
        <p>This is lexical passage retrieval, not an AI-generated answer. Sources are federal guidance and may be outdated or incomplete; verify the source directly. Search only public topics—don’t enter personal or confidential data.</p>
      </section>
    </>
  );
}

function AssistantView({ dataset }: { dataset: DatasetContext }) {
  const [mode, setMode] = useState<"dataset" | "guidance">("dataset");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<GroundedAnswer | null>(null);
  const [answerError, setAnswerError] = useState("");
  const [answering, setAnswering] = useState(false);

  async function askQuestion(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "dataset" && dataset.transaction_count < 1) {
      setAnswerError("Load a CSV or demo dataset before asking about transaction data.");
      return;
    }
    setAnswer(null);
    setAnswerError("");
    setAnswering(true);
    try {
      const response = await fetch("/api/v1/public-library/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, ...(mode === "dataset" ? { dataset } : {}) }),
      });
      const payload: unknown = await response.json();
      if (!response.ok) {
        const detail = typeof payload === "object" && payload !== null && "detail" in payload && typeof payload.detail === "string"
          ? payload.detail
          : "The local answer service is unavailable.";
        throw new Error(detail);
      }
      if (!isGroundedAnswer(payload)) throw new Error("The answer service returned an invalid response.");
      setAnswer(payload);
    } catch (reason) {
      setAnswerError(reason instanceof Error ? reason.message : "The question could not be answered.");
    } finally {
      setAnswering(false);
    }
  }

  return (
    <>
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />DATA-AWARE ASSISTANT</div><h1>AI assistant</h1><p>Analyze your current dataset or ask a separate public finance question.</p></div></div>
      <section className="panel assistant-panel">
        <div className="assistant-orb"><MessageSquareText size={25} /></div>
        <div className="assistant-mode-switch" role="group" aria-label="Assistant question mode">
          <button aria-pressed={mode === "dataset"} className={mode === "dataset" ? "selected" : ""} onClick={() => { setMode("dataset"); setAnswer(null); setAnswerError(""); }} type="button">Analyze this dataset</button>
          <button aria-pressed={mode === "guidance"} className={mode === "guidance" ? "selected" : ""} onClick={() => { setMode("guidance"); setAnswer(null); setAnswerError(""); }} type="button">Public finance guidance</button>
        </div>
        <h2>{mode === "dataset"
          ? `Ask about ${dataset.source_kind === "demo" ? "the demo dataset" : "your CSV"}`
          : "Ask a public finance question"}</h2>
        <p>{mode === "dataset"
          ? "Get insights from transaction totals, monthly trends, and categories."
          : "Answers use retrieved public SBA/IRS passages and include source links."}</p>
        {mode === "dataset" && (
          <div className="dataset-context-pill"><Database size={14} />{dataset.source_name} · {dataset.transaction_count.toLocaleString()} rows · {dataset.source_kind === "demo" ? "public demo" : "local CSV"}</div>
        )}
        <form className="assistant-input-wrap" onSubmit={(event) => void askQuestion(event)}>
          <input
            aria-label="Ask a question"
            maxLength={500}
            minLength={3}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={mode === "dataset" ? "What are my biggest outflows?" : "How can a small business manage cash flow?"}
            value={question}
          />
          <button
            aria-label="Send question"
            disabled={answering || question.trim().length < 3 || (mode === "dataset" && dataset.transaction_count < 1)}
            type="submit"
          >
            {answering ? <LoaderCircle className="spin" size={17} /> : <ArrowRight size={17} />}
          </button>
        </form>
        {answering && <p className="assistant-safety" role="status">{mode === "dataset" ? "Analyzing aggregate transaction data with the local model…" : "Checking public sources with the local model…"}</p>}
        {answerError && <p className="search-message" role="alert">{answerError}</p>}
        {answer && (
          <div className="assistant-response" aria-live="polite">
            <div className="results-heading">{answer.abstained ? "Evidence not found" : `Answer · ${answer.model}`}</div>
            <p>{answer.answer}</p>
            {answer.data_based && (
              <>
                <div className="dataset-facts">
                  <div className="results-heading">Calculated from this dataset</div>
                  {dataset.currencies.map((summary) => (
                    <div className="dataset-fact-row" key={summary.currency}>
                      <strong>{summary.currency === "XXX" ? "Currency unknown" : summary.currency}</strong>
                      <span>Inflows {formatTransactionAmount(summary.inflow, summary.currency)}</span>
                      <span>Outflows {formatTransactionAmount(summary.outflow, summary.currency)}</span>
                      <span>Net {formatTransactionAmount(summary.inflow - summary.outflow, summary.currency)}</span>
                    </div>
                  ))}
                  {dataset.currencies.flatMap((summary) =>
                    dataset.categories
                      .filter((category) => category.currency === summary.currency && category.outflow > 0)
                      .slice(0, 3),
                  ).map((category, index) => (
                    <div className="dataset-fact-row" key={`${category.currency}-${category.category}`}>
                      <strong>{index === 0 ? "Largest outflow category" : "Outflow category"}: {category.category} · {category.currency}</strong>
                      <span>{formatTransactionAmount(category.outflow, category.currency)} · {category.transactions} rows</span>
                    </div>
                  ))}
                </div>
                <div className="assistant-data-source"><Database size={13} />Aggregate-only summary from {dataset.source_name}; raw rows and descriptions stay in this browser.</div>
              </>
            )}
            {answer.citations.length > 0 && (
              <div className="assistant-citations">
                <div className="results-heading">Sources</div>
                {answer.citations.map((citation) => (
                  <article className="source-result" key={citation.chunk_id}>
                    <div className="result-meta">{citation.publisher} · {citation.edition}{citation.section ? ` · ${citation.section}` : ""}</div>
                    <p>{citation.excerpt}</p>
                    <a href={citation.url} rel="noreferrer" target="_blank">{citation.title} <ArrowUpRight size={12} /></a>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
        <div className="assistant-safety"><ShieldCheck size={14} />{mode === "dataset"
          ? "Ollama runs locally. Only aggregate totals, dates, currency, and category summaries are sent—not raw rows or descriptions."
          : "Ollama runs locally; retrieved SBA/IRS public excerpts are used as evidence."}</div>
      </section>
    </>
  );
}

type TrendMethod = "Last period" | "3-period average" | "Linear trend";

type TrendScore = {
  method: TrendMethod;
  mae: number;
  rmse: number;
  smape: number;
};

type TrendRun = {
  interval: "day" | "month";
  holdoutCount: number;
  mae: number;
  rmse: number;
  smape: number;
  method: TrendMethod;
  scores: TrendScore[];
  backtest: { month: string; actual: number; estimate: number }[];
  forecasts: { month: string; estimate: number }[];
};

type TrendPoint = { month: string; net: number; time: number };

function linearTrend(points: TrendPoint[], x: number) {
  const meanX = points.reduce((sum, point) => sum + point.time, 0) / points.length;
  const meanY = points.reduce((sum, point) => sum + point.net, 0) / points.length;
  const denominator = points.reduce((sum, point) => sum + (point.time - meanX) ** 2, 0);
  const slope = denominator
    ? points.reduce((sum, point) => sum + (point.time - meanX) * (point.net - meanY), 0) / denominator
    : 0;
  return meanY + slope * (x - meanX);
}

function predictTrend(method: TrendMethod, history: TrendPoint[], time: number) {
  if (method === "Linear trend") return linearTrend(history, time);
  if (method === "3-period average") {
    const window = history.slice(-3);
    return window.reduce((sum, point) => sum + point.net, 0) / window.length;
  }
  return history[history.length - 1].net;
}

function scorePredictions(
  method: TrendMethod,
  actual: TrendPoint[],
  predictions: number[],
): TrendScore {
  const errors = actual.map((point, index) => point.net - predictions[index]);
  const mae = errors.reduce((sum, error) => sum + Math.abs(error), 0) / errors.length;
  const rmse = Math.sqrt(errors.reduce((sum, error) => sum + error ** 2, 0) / errors.length);
  const smape = actual.reduce((sum, point, index) => {
    const denominator = Math.abs(point.net) + Math.abs(predictions[index]);
    return sum + (denominator ? 200 * Math.abs(errors[index]) / denominator : 0);
  }, 0) / actual.length;
  return { method, mae, rmse, smape };
}

function trainTrendBaseline(series: TrendPoint[], interval: "day" | "month"): TrendRun {
  const holdoutCount = Math.max(1, Math.floor(series.length * 0.2));
  const trainingCount = series.length - holdoutCount;
  const holdout = series.slice(trainingCount);
  const methods: TrendMethod[] = ["Last period", "3-period average", "Linear trend"];
  const candidateRuns = methods.map((method) => {
    const predictions = holdout.map((point, index) =>
      predictTrend(method, series.slice(0, trainingCount + index), point.time),
    );
    return {
      score: scorePredictions(method, holdout, predictions),
      predictions,
    };
  });
  const selected = candidateRuns.reduce((best, candidate) =>
    candidate.score.mae < best.score.mae ? candidate : best,
  );
  const { method, mae, rmse, smape } = selected.score;
  const allPoints = series;
  const lastPeriod = series[series.length - 1].month;
  const forecasts = [0, 1, 2].map((offset) => {
    const date = interval === "day"
      ? new Date(`${lastPeriod}T00:00:00Z`)
      : new Date(`${lastPeriod}-01T00:00:00Z`);
    if (interval === "day") date.setUTCDate(date.getUTCDate() + offset + 1);
    else date.setUTCMonth(date.getUTCMonth() + offset + 1);
    const key = interval === "day"
      ? date.toISOString().slice(0, 10)
      : date.toISOString().slice(0, 7);
    const time = interval === "day"
      ? Date.parse(`${key}T00:00:00Z`) / 86_400_000
      : Number(key.slice(0, 4)) * 12 + Number(key.slice(5, 7)) - 1;
    return { month: key, estimate: predictTrend(method, allPoints, time) };
  });
  return {
    interval,
    holdoutCount,
    mae,
    rmse,
    smape,
    method,
    scores: candidateRuns.map((candidate) => candidate.score).sort((left, right) => left.mae - right.mae),
    backtest: holdout.map((point, index) => ({
      month: point.month,
      actual: point.net,
      estimate: selected.predictions[index],
    })),
    forecasts,
  };
}

function ModelsView({
  modelInterval, modelSeries, modelCurrency, onTrain, onView, run, sourceKind, sourceName,
}: {
  modelSeries: TrendPoint[];
  modelInterval: "day" | "month";
  modelCurrency: string;
  onTrain: (run: TrendRun) => void;
  onView: (view: View) => void;
  run: TrendRun | null;
  sourceKind: "demo" | "local";
  sourceName: string;
}) {
  const canTrain = modelSeries.length >= 5;
  const dataLabel = sourceKind === "demo" ? "sales less returns" : "net transaction movement";

  return (
    <>
      <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" />MODEL OPERATIONS</div><h1>Model lab</h1><p>Compare forecasting baselines with a chronological walk-forward backtest.</p></div><span className={`readiness-state ${run ? "ready" : "pending"}`}>{run ? `${run.method} selected` : "Ready to train"}</span></div>
      <section className="panel model-status-panel">
        <div className="model-status-head"><div className="model-status-icon"><Sparkles size={20} /></div><div><span className="eyebrow">LOCAL MODEL COMPARISON</span><h2>{run ? `${run.method} selected after backtesting` : "Train on the current transaction timeline"}</h2></div></div>
        <p>Compares last-period, three-period moving-average, and linear-trend forecasts of {modelInterval === "month" ? "monthly" : "daily"} {dataLabel} using sequential walk-forward predictions on the latest chronological holdout. The lowest holdout MAE is selected. Forecasts run in this browser; no rows are uploaded.</p>
        <div className="model-facts">
          <div><span>Training dataset</span><strong>{sourceName}</strong></div>
          <div><span>Dated {modelInterval === "month" ? "monthly" : "daily"} points</span><strong>{modelSeries.length}</strong></div>
          <div><span>Backtest holdout</span><strong>{run ? `${run.holdoutCount} period${run.holdoutCount === 1 ? "" : "s"}` : "Not run"}</strong></div>
          <div><span>Selected MAE</span><strong>{run ? formatMoney(run.mae, modelCurrency, 2) : "Not measured"}</strong></div>
        </div>
        <div className="heading-actions">
          <button className="button button-primary" disabled={!canTrain} onClick={() => onTrain(trainTrendBaseline(modelSeries, modelInterval))} type="button"><Sparkles size={15} />Train & backtest</button>
          <button className="button button-secondary" onClick={() => onView("analysis")} type="button">Review transaction analysis <ArrowRight size={15} /></button>
        </div>
        {!canTrain && <p className="model-requirement">At least five consecutive dated periods in one known currency are needed for a useful holdout comparison. Add or select a suitable CSV to continue.</p>}
        {run && (
          <>
            <div className="model-score-list">
              {run.scores.map((score) => (
                <div key={score.method} className={score.method === run.method ? "selected" : ""}>
                  <strong>{score.method}{score.method === run.method ? " · selected" : ""}</strong>
                  <span>MAE {formatMoney(score.mae, modelCurrency, 2)}</span>
                  <span>RMSE {formatMoney(score.rmse, modelCurrency, 2)}</span>
                  <span>sMAPE {score.smape.toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <div className="model-backtest-panel">
              <div className="panel-heading"><div><h2>Walk-forward holdout</h2><p>Actual movement compared with the selected model</p></div></div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={run.backtest} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid stroke="#edf0ec" vertical={false} />
                    <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 9 }} dy={8} />
                    <YAxis axisLine={false} tickLine={false} tick={{ fill: "#98a29b", fontSize: 10 }} width={48} />
                    <Tooltip formatter={(value) => formatMoney(Number(value), modelCurrency, 2)} />
                    <Line dataKey="actual" name="Actual" stroke="#526d83" strokeWidth={2} dot={{ r: 3 }} />
                    <Line dataKey="estimate" name="Backtest estimate" stroke="#5da47b" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        )}
        {run && (
          <div className="model-forecast-grid" aria-live="polite">
            {run.forecasts.map((item) => (
              <div key={item.month}><span>{item.month}</span><strong>{formatMoney(item.estimate, modelCurrency)}</strong><small>{run.interval} movement estimate · exploratory</small></div>
            ))}
          </div>
        )}
      </section>
      <section className="panel data-caveat">
        <div className="caveat-mark"><CircleHelp size={16} /></div>
        <div><strong>Review data coverage and holdout size</strong><p>{modelSeries.length < 12
          ? `This dataset has only ${modelSeries.length} dated ${modelInterval === "month" ? "months" : "days"}; the holdout is too small to judge predictive quality. `
          : ""}{sourceKind === "demo"
          ? "UCI Online Retail is historic invoice-line sales and returns, not cash receipts or payments; it is useful for exploring trend comparison only."
          : "Your file may contain sales or non-cash transactions. Confirm the source rows represent actual cash movements before using balance projection."} Holdout metrics are retrospective diagnostics, not a guarantee of future performance.</p></div>
      </section>
    </>
  );
}

export default App;
