/** One in-flight read per feed, no hidden/offline polls, bounded reconnect backoff. */
export type PollEnvironment = {
  active: () => boolean;
  schedule: (run: () => void, delay: number) => unknown;
  cancel: (timer: unknown) => void;
  listen: (wake: () => void) => () => void;
};
const browser: PollEnvironment = {
  active: () => !document.hidden && navigator.onLine !== false,
  schedule: (run, delay) => window.setTimeout(run, delay),
  cancel: timer => window.clearTimeout(timer as number),
  listen(wake) {
    document.addEventListener("visibilitychange", wake);
    for (const name of ["online", "offline", "focus"]) window.addEventListener(name, wake);
    return () => {
      document.removeEventListener("visibilitychange", wake);
      for (const name of ["online", "offline", "focus"]) window.removeEventListener(name, wake);
    };
  },
};

export function visiblePoll(run: (signal: AbortSignal) => Promise<void>, intervalMs: number,
  environment: PollEnvironment = browser, onWake: () => void = () => {}) {
  let stopped = false, running = false, again = false, failures = 0;
  let timer: unknown, controller: AbortController | undefined;
  const clear = () => { if (timer !== undefined) environment.cancel(timer); timer = undefined; };
  async function poll() {
    clear();
    if (stopped || !environment.active()) return;
    if (running) { again = true; return; }
    running = true; controller = new AbortController();
    const current = controller;
    try { await run(current.signal); if (!current.signal.aborted) failures = 0; }
    catch { if (!current.signal.aborted) failures = Math.min(failures + 1, 5); }
    finally {
      running = false;
      if (!stopped && environment.active()) {
        const delay = again ? 0 : Math.min(30000, intervalMs * 2 ** failures);
        again = false; timer = environment.schedule(() => void poll(), delay);
      }
    }
  }
  function wake() {
    onWake(); clear();
    if (!environment.active()) { controller?.abort(); again = false; return; }
    if (running) { again = true; return; }
    void poll();
  }
  const unlisten = environment.listen(wake);
  wake();
  return () => { stopped = true; clear(); controller?.abort(); unlisten(); };
}
