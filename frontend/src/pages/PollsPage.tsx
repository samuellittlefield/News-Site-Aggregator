import { useGenericBallot, useHouseDistricts, useHousePolls } from "../api/client";
import { ApprovalSection } from "../components/ApprovalSection";
import { DistrictMap } from "../components/DistrictMap";
import { GenericBallotBar } from "../components/GenericBallotBar";
import { PollCarousel } from "../components/PollCarousel";

export function PollsPage() {
  const { polls, loading: pollsLoading } = useHousePolls();
  const { districts, loading: distLoading } = useHouseDistricts();
  const { ballot, loading: ballotLoading } = useGenericBallot();

  const loading = pollsLoading || distLoading || ballotLoading;

  return (
    <div className="min-h-screen bg-gray-950">
      <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">

        {/* Header */}
        <div className="space-y-1">
          <h2 className="text-xl font-bold text-white tracking-tight">2026 House Polling</h2>
          <p className="text-xs text-gray-500">
            {districts.length} competitive districts tracked ·{" "}
            {polls.length > 0 ? `${polls.length} polls` : "Individual district polls loading as cycle progresses"}
          </p>
        </div>

        {/* Generic ballot headline */}
        {!ballotLoading && <GenericBallotBar ballot={ballot} />}

        {/* Presidential approval (Economist/YouGov) */}
        <ApprovalSection />

        {/* 3D district map */}
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">
            Competitive Districts — 3D Polling Signal Map
          </p>
          <p className="text-[10px] text-gray-700">
            Height = polling intensity · Color = partisan lean · Source: Cook Political Report 2026 ratings + Wikipedia polls
          </p>
          {distLoading ? (
            <div className="h-96 bg-gray-900 rounded-xl animate-pulse" />
          ) : (
            <DistrictMap districts={districts} />
          )}
        </div>

        {/* Poll carousel */}
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">Recent Polls</p>
          {loading ? (
            <div className="h-24 bg-gray-900 rounded-xl animate-pulse" />
          ) : (
            <PollCarousel polls={polls} ballot={ballot} />
          )}
        </div>

      </div>
    </div>
  );
}
