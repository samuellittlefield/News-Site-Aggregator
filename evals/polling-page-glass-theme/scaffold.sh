#!/bin/bash
# Rewinds just the implementation to its pre-feature state, so the agent has
# a real feature to build. The planning docs stay at HEAD (they already
# exist ahead of implementation in the real workflow, written by the
# news-site-feature-pipeline skill before Claude Code ever sees the ticket).
set -e
git checkout 4d735d2 -- \
  frontend/src/components/ApprovalSection.tsx \
  frontend/src/components/DistrictMap.tsx \
  frontend/src/components/ForecastSection.tsx \
  frontend/src/components/GenericBallotBar.tsx \
  frontend/src/components/ModelControls.tsx \
  frontend/src/components/PollCarousel.tsx \
  frontend/src/components/RecentPollsList.tsx \
  frontend/src/components/SourcesDisclosure.tsx \
  frontend/src/components/VoteHubApprovalCard.tsx \
  frontend/src/pages/PollsPage.tsx \
  frontend/tailwind.config.js
