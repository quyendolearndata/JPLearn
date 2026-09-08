import type { CatalogItemPublic } from "@jplearn/domain";

export interface MediaRecoveryCycle {
  targetItemId: string | null;
  automaticRefetches: number;
  refetchInFlight: boolean;
  generation: number;
}

export type AutomaticCatalogRefetchDecision = {
  action: "refetch" | "coalesced" | "exhausted";
  cycle: MediaRecoveryCycle;
};

export type SessionCatalogSelection =
  | { kind: "selected"; item: CatalogItemPublic; choseDefault: boolean }
  | { kind: "unavailable"; targetItemId: string }
  | { kind: "empty" };

export function createMediaRecoveryCycle(targetItemId: string | null): MediaRecoveryCycle {
  return {
    targetItemId,
    automaticRefetches: 0,
    refetchInFlight: false,
    generation: 0,
  };
}

export function reconcileMediaRecoveryTarget(
  cycle: MediaRecoveryCycle,
  targetItemId: string | null,
): MediaRecoveryCycle {
  return cycle.targetItemId === targetItemId
    ? cycle
    : { ...createMediaRecoveryCycle(targetItemId), generation: cycle.generation + 1 };
}

export function requestAutomaticCatalogRefetch(
  cycle: MediaRecoveryCycle,
): AutomaticCatalogRefetchDecision {
  if (cycle.refetchInFlight) return { action: "coalesced", cycle };
  if (cycle.automaticRefetches >= 1) return { action: "exhausted", cycle };
  return {
    action: "refetch",
    cycle: {
      ...cycle,
      automaticRefetches: cycle.automaticRefetches + 1,
      refetchInFlight: true,
    },
  };
}

export function completeAutomaticCatalogRefetch(cycle: MediaRecoveryCycle): MediaRecoveryCycle {
  return { ...cycle, refetchInFlight: false };
}

export function restartMediaRecoveryManually(cycle: MediaRecoveryCycle): MediaRecoveryCycle {
  return {
    ...createMediaRecoveryCycle(cycle.targetItemId),
    generation: cycle.generation + 1,
  };
}

export function selectSessionCatalogItem(
  items: CatalogItemPublic[],
  targetItemId: string | null,
): SessionCatalogSelection {
  if (targetItemId) {
    const selected = items.find((item) => item.id === targetItemId);
    return selected
      ? { kind: "selected", item: selected, choseDefault: false }
      : { kind: "unavailable", targetItemId };
  }
  const selected = items.find((item) => item.hls_url ?? item.playback_url) ?? items[0];
  if (!selected) return { kind: "empty" };
  return { kind: "selected", item: selected, choseDefault: true };
}
