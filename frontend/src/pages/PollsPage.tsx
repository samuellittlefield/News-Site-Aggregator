import { useGenericBallot, useHouseDistricts, useHousePolls } from "../api/client";
import { ApprovalSection } from "../components/ApprovalSection";
import { DistrictMap } from "../components/DistrictMap";
import { ForecastSection } from "../components/ForecastSection";
import { GenericBallotBar } from "../components/GenericBallotBar";
import { PollCarousel } from "../components/PollCarousel";
import { RecentPollsList } from "../components/RecentPollsList";
import { SourcesDisclosure } from "../components/SourcesDisclosure";
import { VoteHubApprovalCard } from "../components/VoteHubApprovalCard";

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
            All {districts.length} House districts ·{" "}
            {polls.length > 0 ? `${polls.length} polls` : "Individual district polls loading as cycle progresses"}
          </p>
        </div>

        {/* Control-of-Congress forecast (prediction markets + model link-outs) */}
        <ForecastSection />

        {/* Generic ballot headline */}
        {!ballotLoading && <GenericBallotBar ballot={ballot} />}

        {/* Presidential approval — VoteHub live average + Economist/YouGov crosstabs */}
        <VoteHubApprovalCard />
        <ApprovalSection />

        {/* District hex cartogram + click-detail panel */}
        <div className="space-y-2">
          <p className="text-xs text-gray-600 uppercase tracking-wider">
            House Districts — Hex Cartogram
          </p>
          <p className="text-[10px] text-gray-700">
            Every district equal-size, colored by 2024 presidential lean · click any district for candidates &amp; fundraising
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

        {/* National polls from VoteHub */}
        <RecentPollsList />

        {/* Where all this data comes from */}
        <SourcesDisclosure />

      </div>
    </div>
  );
}
