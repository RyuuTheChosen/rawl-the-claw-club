export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-5xl font-bold text-rawl-primary mb-4">Rawl</h1>
      <p className="text-xl text-gray-400 mb-8">AI Fighting Game Platform</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl">
        <div className="bg-rawl-secondary rounded-lg p-6 border border-gray-800">
          <h2 className="text-lg font-semibold text-rawl-accent mb-2">Watch</h2>
          <p className="text-gray-400 text-sm">
            Spectate live AI fighter matches in real-time
          </p>
        </div>
        <div className="bg-rawl-secondary rounded-lg p-6 border border-gray-800">
          <h2 className="text-lg font-semibold text-rawl-accent mb-2">Train</h2>
          <p className="text-gray-400 text-sm">
            Train your own AI fighters using reinforcement learning
          </p>
        </div>
        <div className="bg-rawl-secondary rounded-lg p-6 border border-gray-800">
          <h2 className="text-lg font-semibold text-rawl-accent mb-2">Compete</h2>
          <p className="text-gray-400 text-sm">
            Enter the ranked ladder and climb the leaderboard
          </p>
        </div>
      </div>
    </main>
  );
}
