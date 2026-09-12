import type { MetadataRoute } from "next";

const publicBaseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://loanhub.co.ls";

export default function sitemap(): MetadataRoute.Sitemap {
    const routes = [
        "",
        "/manual",
        "/documentation",
        "/borrower-registration",
        "/register-company-admin",
        "/lender-access",
        "/choose-account-type",
        "/privacy/loanhub-mobile",
    ];

    return routes.map((route, index) => ({
        url: `${publicBaseUrl}${route}`,
        lastModified: new Date(),
        changeFrequency: index === 0 ? "daily" : "weekly",
        priority: index === 0 ? 1 : route === "/manual" || route === "/documentation" ? 0.8 : 0.7,
    }));
}
