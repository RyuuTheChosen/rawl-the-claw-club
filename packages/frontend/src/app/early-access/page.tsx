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

function Divider() {
  return (
    <div className="mx-auto w-full max-w-xs">
      <div className="h-px bg-gradient-to-r from-transparent via-border to-transparent" />
    </div>
  );
}

export default function EarlyAccessPage() {
  return (
    <PageTransition>
      <div className="flex flex-col items-center">
        <EarlyAccessHero />
        <Divider />
        <ValueProps />
        <Divider />
        <LandingHowItWorks />
        <Divider />
        <LandingGames />
        <Divider />
        <EarlyAccessCTA />
      </div>
    </PageTransition>
  );
}
