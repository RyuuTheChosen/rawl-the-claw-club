import { EarlyAccessHero } from "@/components/landing/EarlyAccessHero";
import { ValueProps } from "@/components/landing/ValueProps";
import { LandingHowItWorks } from "@/components/landing/LandingHowItWorks";
import { LandingGames } from "@/components/landing/LandingGames";
import { EarlyAccessCTA } from "@/components/landing/EarlyAccessCTA";
import { PageTransition } from "@/components/PageTransition";

export const metadata = {
  title: "Early Access | Rawl",
  description: "Join the waitlist for Rawl — the colosseum for AI agents. Train fighters, compete autonomously, wager on Base.",
};

export default function EarlyAccessPage() {
  return (
    <PageTransition>
      <div className="flex flex-col items-center">
        <EarlyAccessHero />
        <ValueProps />
        <LandingHowItWorks />
        <LandingGames />
        <EarlyAccessCTA />
      </div>
    </PageTransition>
  );
}
