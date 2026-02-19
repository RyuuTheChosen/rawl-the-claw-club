import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://rawl.gg";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: BASE_URL, changeFrequency: "daily", priority: 1.0 },
    { url: `${BASE_URL}/lobby`, changeFrequency: "always", priority: 0.9 },
    { url: `${BASE_URL}/leaderboard`, changeFrequency: "hourly", priority: 0.8 },
    { url: `${BASE_URL}/bets`, changeFrequency: "hourly", priority: 0.7 },
    { url: `${BASE_URL}/dashboard`, changeFrequency: "weekly", priority: 0.6 },
  ];
}
