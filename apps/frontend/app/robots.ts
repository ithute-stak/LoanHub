import type { MetadataRoute } from "next";

const publicBaseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://loanhub.co.ls";

export default function robots(): MetadataRoute.Robots {
    return {
        rules: {
            userAgent: "*",
            allow: ["/", "/manual", "/documentation", "/privacy/"],
            disallow: [
                "/superadmin/",
                "/company/",
                "/borrower/",
                "/platform/",
            ],
        },
        sitemap: `${publicBaseUrl}/sitemap.xml`,
    };
}
