import { DEFAULT_FLAGS, minutesFromDuration, ZOMBIE_SESSION_SECONDS } from "./index";

test("FR-FLG-001 flags default false", () => {
  expect(DEFAULT_FLAGS).toEqual({
    speaking_enabled: false,
    l1_subtitles_enabled: false,
    grammar_enabled: false,
    flashcards_enabled: false,
  });
});

test("FR-PRG-001 minutes floor; zombie adds zero", () => {
  expect(minutesFromDuration(119)).toBe(1);
  expect(minutesFromDuration(ZOMBIE_SESSION_SECONDS + 1)).toBe(0);
});

test("Batch A-D domain contracts type validation", () => {
  import("./index").then((domain) => {
    expect(domain).toBeDefined();
    expect(domain.minutesFromDuration).toBeInstanceOf(Function);
  });
});
