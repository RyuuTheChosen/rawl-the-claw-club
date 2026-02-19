import { HeroSection } from "@/components/landing/HeroSection";
import { HowItWorks } from "@/components/HowItWorks";
import { LiveStatsBar } from "@/components/LiveStatsBar";
import { FeaturedMatch } from "@/components/FeaturedMatch";
import { GamesShowcase } from "@/components/GamesShowcase";
import { PageTransition } from "@/components/PageTransition";

export default function Home() {
  return (
    <PageTransition>
      <div className="flex flex-col items-center">
        <HeroSection />
        <HowItWorks />
        <LiveStatsBar />
        <FeaturedMatch />
        <GamesShowcase />
      </div>
    </PageTransition>
  );
}
