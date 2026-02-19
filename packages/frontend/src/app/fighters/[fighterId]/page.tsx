"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Swords, Trophy, X, Percent } from "lucide-react";
import { Fighter, Match } from "@/types";
import { getFighter, getMatches } from "@/lib/api";
import { MatchCard } from "@/components/MatchCard";
import { ArcadeCard } from "@/components/ArcadeCard";
import { ArcadeLoader } from "@/components/ArcadeLoader";
import { StatusBadge } from "@/components/StatusBadge";
import { DivisionBadge } from "@/components/DivisionBadge";
import { PageTransition } from "@/components/PageTransition";
import { StaggeredList } from "@/components/StaggeredList";

export default function FighterProfilePage() {
  const params = useParams();
  const fighterId = params.fighterId as string;
  const [fighter, setFighter] = useState<Fighter | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getFighter(fighterId),
      getMatches({ fighter_id: fighterId }),
    ])
      .then(([f, m]) => {
        setFighter(f);
        setMatches(m.items);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [fighterId]);

  if (loading) {
    return <ArcadeLoader fullPage text="LOADING FIGHTER" />;
  }

  if (!fighter) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-2">
        <span className="font-pixel text-sm text-neon-red">FIGHTER NOT FOUND</span>
      </div>
    );
  }

  const winRate =
    fighter.matches_played > 0
      ? ((fighter.wins / fighter.matches_played) * 100).toFixed(1)
      : "0.0";

  const stats = [
    { icon: Swords, label: "MATCHES", value: fighter.matches_played, color: "text-foreground" },
    { icon: Trophy, label: "WINS", value: fighter.wins, color: "text-neon-green" },
    { icon: X, label: "LOSSES", value: fighter.losses, color: "text-neon-red" },
    { icon: Percent, label: "WIN RATE", value: `${winRate}%`, color: "text-neon-cyan" },
  ];

  return (
    <PageTransition>
      <div className="mx-auto max-w-4xl px-4 py-6">
        {/* Character card header */}
        <ArcadeCard hover={false} className="mb-6">
          <div className="flex items-start justify-between">
            <div>
              <h1 className="font-pixel text-sm text-neon-orange text-glow-orange sm:text-base">
                {fighter.name}
              </h1>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="font-pixel text-[10px] uppercase text-muted-foreground">
                  {fighter.game_id}
                </span>
                <span className="text-xs text-muted-foreground">{fighter.character}</span>
                <StatusBadge status={fighter.status} />
                <DivisionBadge division={fighter.division_tier} />
              </div>
            </div>
            <div className="text-right">
              <div className="font-mono text-3xl text-neon-orange text-glow-orange">
                {fighter.elo_rating.toFixed(0)}
              </div>
              <div className="font-pixel text-[10px] text-muted-foreground">ELO RATING</div>
            </div>
          </div>

          {/* Stat blocks */}
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="flex flex-col items-center rounded-md bg-muted/30 p-3"
              >
                <s.icon className={`mb-1 h-4 w-4 ${s.color}`} />
                <div className={`font-mono text-xl font-bold ${s.color}`}>
                  {s.value}
                </div>
                <div className="font-pixel text-[9px] text-muted-foreground">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </ArcadeCard>

        <h2 className="mb-4 font-pixel text-xs text-foreground">RECENT MATCHES</h2>
        {matches.length === 0 ? (
          <div className="flex min-h-[20vh] items-center justify-center">
            <span className="font-pixel text-[10px] text-muted-foreground">
              NO MATCHES YET
            </span>
          </div>
        ) : (
          <StaggeredList className="grid gap-4 sm:grid-cols-2">
            {matches.map((match) => (
              <MatchCard key={match.id} match={match} />
            ))}
          </StaggeredList>
        )}
      </div>
    </PageTransition>
  );
}
