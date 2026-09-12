import { api } from "@/lib/api";
import { getStoredValue, StorageKeys } from "@/lib/storage";

export type DocumentGenerationBrand = {
  companyId: string | null;
  companyName: string | null;
  companyLogoDataUrl: string | null;
};

type CompanyBrandingResponse = {
  company_id: string;
  right_logo_download_url?: string | null;
  left_logo_download_url?: string | null;
};

type CompanySummary = {
  id: string;
  name: string;
};

type BrandCacheEntry = {
  expiresAt: number;
  value: DocumentGenerationBrand;
};

export type DocumentGenerationWindowOptions = {
  title: string;
  description?: string;
  companyId?: string | null;
  companyName?: string | null;
};

const BRAND_CACHE_TTL_MS = 2 * 60 * 1000;
const brandCache = new Map<string, BrandCacheEntry>();
const brandRequests = new Map<string, Promise<DocumentGenerationBrand>>();

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeCompanyId(companyId?: string | null): string | null {
  const explicit = companyId?.trim();
  if (explicit) return explicit;
  return getStoredValue(StorageKeys.activeCompanyId);
}

function companyInitials(value: string | null | undefined): string {
  const words = String(value ?? "Company")
    .trim()
    .split(/\s+/)
    .filter(Boolean);

  if (words.length === 0) return "CO";
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join("");
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error ?? new Error("Could not read company logo."));
    reader.readAsDataURL(blob);
  });
}

async function fetchCompanyLogoDataUrl(downloadUrl: string | null | undefined): Promise<string | null> {
  if (!downloadUrl) return null;

  try {
    const response = await api.get<Blob>(downloadUrl, {
      responseType: "blob",
      headers: { Accept: "image/*" },
    });

    if (!response.data || response.data.size === 0) return null;
    return await blobToDataUrl(response.data);
  } catch {
    return null;
  }
}

/**
 * Resolve the tenant identity used by document-generation waiting windows.
 *
 * The company logo is deliberately fetched through the authenticated Axios
 * client and converted to a data URL. A raw /files/:id/download URL is not
 * placed in <img src> because protected managed files normally require the
 * Authorization header that the browser image request cannot provide.
 */
export async function resolveDocumentGenerationBrand(
  companyId?: string | null,
  companyName?: string | null,
): Promise<DocumentGenerationBrand> {
  const resolvedCompanyId = safeCompanyId(companyId);

  if (!resolvedCompanyId) {
    return {
      companyId: null,
      companyName: companyName?.trim() || null,
      companyLogoDataUrl: null,
    };
  }

  const now = Date.now();
  const cached = brandCache.get(resolvedCompanyId);
  if (cached && cached.expiresAt > now) {
    if (companyName?.trim() && cached.value.companyName !== companyName.trim()) {
      cached.value = { ...cached.value, companyName: companyName.trim() };
    }
    return cached.value;
  }

  const inFlight = brandRequests.get(resolvedCompanyId);
  if (inFlight) return inFlight;

  const request = (async (): Promise<DocumentGenerationBrand> => {
    const brandingPromise = api
      .get<CompanyBrandingResponse>(`/companies/${resolvedCompanyId}/branding`)
      .then((response) => response.data)
      .catch(() => null);

    const companyPromise = companyName?.trim()
      ? Promise.resolve<CompanySummary | null>({ id: resolvedCompanyId, name: companyName.trim() })
      : api
          .get<CompanySummary>(`/companies/${resolvedCompanyId}`)
          .then((response) => response.data)
          .catch(() => null);

    const [branding, company] = await Promise.all([brandingPromise, companyPromise]);

    // The primary/right-side company logo is the authoritative waiting-screen
    // identity. The backend may already resolve a left logo into this slot when
    // no explicit right logo exists, so right_logo_download_url stays first.
    const logoDataUrl = await fetchCompanyLogoDataUrl(
      branding?.right_logo_download_url ?? branding?.left_logo_download_url ?? null,
    );

    const value: DocumentGenerationBrand = {
      companyId: resolvedCompanyId,
      companyName: companyName?.trim() || company?.name?.trim() || null,
      companyLogoDataUrl: logoDataUrl,
    };

    brandCache.set(resolvedCompanyId, {
      expiresAt: Date.now() + BRAND_CACHE_TTL_MS,
      value,
    });

    return value;
  })();

  brandRequests.set(resolvedCompanyId, request);

  try {
    return await request;
  } finally {
    brandRequests.delete(resolvedCompanyId);
  }
}

function buildLoadingHtml(options: DocumentGenerationWindowOptions, brand?: DocumentGenerationBrand | null): string {
  const title = escapeHtml(options.title);
  const description = escapeHtml(
    options.description ?? "Please wait while LoanHub securely prepares the requested PDF.",
  );
  const companyName = escapeHtml(brand?.companyName ?? options.companyName?.trim() ?? "Your company");
  const companyInitial = escapeHtml(companyInitials(brand?.companyName ?? options.companyName));
  const companyLogo = brand?.companyLogoDataUrl
    ? `<img id="loanhub-company-logo" src="${escapeHtml(brand.companyLogoDataUrl)}" alt="${companyName} logo" />`
    : `<span id="loanhub-company-initials" class="company-initials">${companyInitial}</span>`;
  const systemLogo = `${window.location.origin}/loanhub-horizontal-logo.png`;

  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Preparing document · LoanHub</title>
  <style>
    :root {
      color-scheme: light;
      --navy: #102a43;
      --blue: #0b69b7;
      --blue-soft: #e9f3fb;
      --green: #15803d;
      --muted: #64748b;
      --line: #dbe6ef;
      --surface: #ffffff;
      --background: #eef4f8;
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 28px;
      background: var(--background);
      color: var(--navy);
      font-family: Arial, Helvetica, sans-serif;
    }
    .workspace {
      width: min(680px, 100%);
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 26px;
      background: var(--surface);
      box-shadow: 0 22px 55px rgba(15, 42, 67, 0.14);
    }
    .accent {
      height: 6px;
      background: linear-gradient(90deg, #0b69b7 0 48%, #21a366 48% 100%);
    }
    .content { padding: 30px; }
    .brand-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      align-items: center;
      gap: 18px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }
    .brand-side {
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-side.company { justify-content: flex-end; text-align: right; }
    .brand-box {
      width: 96px;
      height: 58px;
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 15px;
      background: #fff;
      padding: 9px;
    }
    .brand-box img { width: 100%; height: 100%; object-fit: contain; display: block; }
    .company-initials {
      width: 100%;
      height: 100%;
      display: grid;
      place-items: center;
      border-radius: 10px;
      background: var(--blue-soft);
      color: var(--blue);
      font-size: 18px;
      font-weight: 900;
      letter-spacing: .05em;
    }
    .brand-copy { min-width: 0; }
    .brand-label {
      margin: 0 0 4px;
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      letter-spacing: .15em;
      text-transform: uppercase;
    }
    .brand-name {
      margin: 0;
      overflow: hidden;
      color: var(--navy);
      font-size: 13px;
      font-weight: 800;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .bridge {
      display: flex;
      align-items: center;
      gap: 6px;
      color: #94a3b8;
    }
    .bridge span { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
    .document {
      padding: 28px 0 4px;
      text-align: center;
    }
    .eyebrow {
      margin: 0;
      color: var(--blue);
      font-size: 11px;
      font-weight: 900;
      letter-spacing: .18em;
      text-transform: uppercase;
    }
    h1 {
      margin: 10px auto 0;
      max-width: 560px;
      font-size: clamp(21px, 3vw, 29px);
      line-height: 1.2;
      letter-spacing: -.02em;
    }
    .description {
      margin: 10px auto 0;
      max-width: 530px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }
    .loader-wrap {
      margin: 24px auto 0;
      width: min(500px, 100%);
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #f8fbfd;
      text-align: left;
    }
    .loader-head { display: flex; align-items: center; gap: 13px; }
    .spinner {
      width: 34px;
      height: 34px;
      flex: 0 0 auto;
      border: 4px solid #d7e8f5;
      border-top-color: var(--blue);
      border-radius: 50%;
      animation: spin .9s linear infinite;
    }
    .status-title { margin: 0; font-size: 14px; font-weight: 900; }
    .status-copy { margin: 3px 0 0; color: var(--muted); font-size: 12px; }
    .progress-track {
      height: 5px;
      margin-top: 16px;
      overflow: hidden;
      border-radius: 999px;
      background: #dfeaf2;
    }
    .progress-bar {
      width: 42%;
      height: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--blue), #38a3db, #21a366);
      animation: loading 1.45s ease-in-out infinite alternate;
    }
    .steps {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 8px;
      margin-top: 14px;
    }
    .step {
      min-width: 0;
      padding: 8px 9px;
      border-radius: 10px;
      background: #fff;
      color: var(--muted);
      font-size: 10px;
      font-weight: 800;
      text-align: center;
    }
    .step.active { background: var(--blue-soft); color: var(--blue); }
    .footer {
      margin: 18px 0 0;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
      text-align: center;
    }
    .error-actions { display: none; margin-top: 14px; text-align: center; }
    .error-actions button {
      border: 1px solid var(--line);
      border-radius: 11px;
      background: #fff;
      color: var(--navy);
      cursor: pointer;
      padding: 9px 14px;
      font: inherit;
      font-size: 12px;
      font-weight: 800;
    }
    body[data-state="error"] .spinner,
    body[data-state="error"] .progress-track,
    body[data-state="error"] .steps { display: none; }
    body[data-state="error"] .loader-wrap { border-color: #fecaca; background: #fff7f7; }
    body[data-state="error"] .status-title { color: #b42318; }
    body[data-state="error"] .error-actions { display: block; }
    @keyframes spin { to { transform: rotate(360deg); } }
    @keyframes loading { from { transform: translateX(-6%); } to { transform: translateX(138%); } }
    @media (max-width: 620px) {
      body { padding: 14px; }
      .content { padding: 22px 18px; }
      .brand-row { grid-template-columns: 1fr; gap: 12px; }
      .bridge { display: none; }
      .brand-side.company { justify-content: flex-start; text-align: left; }
      .brand-box { width: 84px; height: 52px; }
      .steps { grid-template-columns: 1fr; }
    }
    @media (prefers-reduced-motion: reduce) {
      .spinner, .progress-bar { animation: none; }
      .progress-bar { width: 72%; transform: none; }
    }
  </style>
</head>
<body data-state="loading">
  <main class="workspace" role="status" aria-live="polite">
    <div class="accent"></div>
    <section class="content">
      <div class="brand-row">
        <div class="brand-side">
          <div class="brand-box"><img src="${escapeHtml(systemLogo)}" alt="LoanHub" /></div>
          <div class="brand-copy">
            <p class="brand-label">System</p>
            <p class="brand-name">LoanHub</p>
          </div>
        </div>
        <div class="bridge" aria-hidden="true"><span></span><span></span><span></span></div>
        <div class="brand-side company">
          <div class="brand-copy">
            <p class="brand-label">Company</p>
            <p id="loanhub-company-name" class="brand-name">${companyName}</p>
          </div>
          <div id="loanhub-company-logo-box" class="brand-box">${companyLogo}</div>
        </div>
      </div>

      <div class="document">
        <p class="eyebrow">Secure document generation</p>
        <h1>${title}</h1>
        <p class="description">${description}</p>
      </div>

      <div class="loader-wrap">
        <div class="loader-head">
          <div class="spinner" aria-hidden="true"></div>
          <div>
            <p id="loanhub-generation-status" class="status-title">Generating PDF document…</p>
            <p id="loanhub-generation-detail" class="status-copy">The document will open automatically when it is ready.</p>
          </div>
        </div>
        <div class="progress-track"><div class="progress-bar"></div></div>
        <div class="steps" aria-hidden="true">
          <div class="step">Secure request</div>
          <div class="step">Apply company identity</div>
          <div class="step active">Render PDF</div>
        </div>
        <div class="error-actions"><button type="button" onclick="window.close()">Close window</button></div>
      </div>

      <p class="footer">Keep this window open. LoanHub is preparing the latest server-generated document, not a cached copy.</p>
    </section>
  </main>
</body>
</html>`;
}

function updateWindowBrand(popup: Window, brand: DocumentGenerationBrand): void {
  if (popup.closed) return;

  try {
    const companyName = popup.document.getElementById("loanhub-company-name");
    const logoBox = popup.document.getElementById("loanhub-company-logo-box");

    if (companyName && brand.companyName) {
      companyName.textContent = brand.companyName;
    }

    if (logoBox && brand.companyLogoDataUrl) {
      logoBox.replaceChildren();
      const image = popup.document.createElement("img");
      image.id = "loanhub-company-logo";
      image.src = brand.companyLogoDataUrl;
      image.alt = brand.companyName ? `${brand.companyName} logo` : "Company logo";
      logoBox.appendChild(image);
    }
  } catch {
    // The popup may already have navigated to the browser PDF viewer.
  }
}

/**
 * Paint the temporary PDF window immediately, then hydrate the right-side
 * company logo without blocking the actual document request.
 */
export function prepareDocumentGenerationWindow(
  popup: Window,
  options: DocumentGenerationWindowOptions,
): void {
  if (popup.closed) return;

  popup.document.open();
  popup.document.write(buildLoadingHtml(options));
  popup.document.close();

  const companyId = safeCompanyId(options.companyId);
  if (!companyId) return;

  void resolveDocumentGenerationBrand(companyId, options.companyName)
    .then((brand) => updateWindowBrand(popup, brand))
    .catch(() => undefined);
}

export function markDocumentGenerationReady(popup: Window): void {
  if (popup.closed) return;
  try {
    const title = popup.document.getElementById("loanhub-generation-status");
    const detail = popup.document.getElementById("loanhub-generation-detail");
    if (title) title.textContent = "PDF ready";
    if (detail) detail.textContent = "Opening the document viewer…";
  } catch {
    // Ignore if the popup has already changed location.
  }
}

export function markDocumentGenerationFailed(
  popup: Window,
  message = "LoanHub could not generate this document. Return to the main window and try again.",
): void {
  if (popup.closed) return;
  try {
    popup.document.body.dataset.state = "error";
    const title = popup.document.getElementById("loanhub-generation-status");
    const detail = popup.document.getElementById("loanhub-generation-detail");
    if (title) title.textContent = "Document generation failed";
    if (detail) detail.textContent = message;
  } catch {
    // Ignore if the popup is no longer controlled by the application.
  }
}
