import { ServiceStatusSection } from "../components/ServiceStatusSection";
import { SourceHealthSection } from "../components/SourceHealthSection";

export function StatusPage() {
  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-10">
      <SourceHealthSection />
      <ServiceStatusSection />
    </main>
  );
}
