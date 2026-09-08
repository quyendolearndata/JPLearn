import { MobilePlaybackTracker, Sample, Transport } from './playbackTracker';
const ok = (body: object = {}) => ({ ok: true, status: 200, json: async () => body });
const playing: Sample = { positionMs: 0, durationMs: 60000, rate: 1, playing: true, ready: true, foreground: true };
function env() {
  let time = 0, nextId = 0;
  const request = jest.fn<ReturnType<Transport>, Parameters<Transport>>().mockResolvedValue(ok());
  const conflict = jest.fn();
  const tracker = new MobilePlaybackTracker(request, () => time, () => `random-${++nextId}`, conflict);
  async function start() { request.mockResolvedValueOnce(ok({ playback_id: 'p1', epoch: 2, initial_position_ms: 1500 })); await tracker.start('clip', 'version-1', 'ipad'); }
  return { tracker, request, conflict, start, at: (value: number) => { time = value; } };
}
test('T-RSM-001 start pins version and iPad class; uncertain retry reuses exact key/body', async () => {
  const e = env(); e.request.mockRejectedValueOnce(new Error('lost response'));
  expect(await e.tracker.start('clip','version-1','ipad')).toBeNull();
  e.request.mockResolvedValueOnce(ok({ playback_id: 'p1', epoch: 2, initial_position_ms: 1500 }));
  expect(await e.tracker.start('clip','version-1','ipad')).toBe(1500);
  expect(e.request.mock.calls[0]).toEqual(e.request.mock.calls[1]);
  expect(JSON.parse(e.request.mock.calls[0][1].body)).toMatchObject({ content_version_id: 'version-1', device_info: { device_class: 'ipad' } });
});
test('T-WAT-001 counts wall time at 2x, excludes seek/buffer/background and includes interval before pause', async () => {
  const e=env(); await e.start(); e.tracker.sample({...playing, rate:2});
  e.at(1000); e.tracker.sample({...playing, rate:2, positionMs:2000});
  e.at(2000); e.tracker.sample({...playing, rate:2, positionMs:4000, playing:false});
  e.at(3000); e.tracker.sample({...playing, positionMs:30000});
  e.at(4000); e.tracker.sample({...playing, positionMs:40000}); // seek jump
  e.at(5000); e.tracker.sample({...playing, positionMs:41000, ready:false});
  e.at(6000); e.tracker.sample({...playing, positionMs:42000, foreground:false});
  await e.tracker.checkpoint();
  expect(JSON.parse(e.request.mock.calls[1][1].body).client_cumulative_active_ms).toBe(2000);
});
test('T-WAT-002 retries uncertain checkpoint byte-for-byte before assigning end seq', async () => {
  const e=env(); await e.start(); e.tracker.sample(playing);e.at(1000);e.tracker.sample({...playing,positionMs:1000});
  e.request.mockRejectedValueOnce(new Error('timeout')); expect(await e.tracker.checkpoint()).toBe(false);
  e.at(2000);e.tracker.sample({...playing,positionMs:2000});
  expect(await e.tracker.end()).toBe(true);
  expect(e.request.mock.calls[1]).toEqual(e.request.mock.calls[2]);
  const last=e.request.mock.calls[3]; expect(last[0]).toBe('/playbacks/p1/end');
  expect(JSON.parse(last[1].body)).toMatchObject({final_seq:2,final_client_cumulative_active_ms:2000,final_client_epoch:2});
});
test('T-WAT-002 a single checkpoint request is in flight; failed end retains final body', async () => {
  const e=env();await e.start();let resolve!: (value: ReturnType<typeof ok>)=>void;
  e.request.mockImplementationOnce(()=>new Promise(r=>{resolve=r;}));
  const first=e.tracker.checkpoint();expect(e.tracker.checkpoint()).toBe(first);resolve(ok());await first;
  e.request.mockRejectedValueOnce(new Error('timeout'));expect(await e.tracker.end()).toBe(false);
  expect(await e.tracker.end()).toBe(true);expect(e.request.mock.calls[2]).toEqual(e.request.mock.calls[3]);
});
test.each([403,404,409])('T-FLG-003 / T-WAT-002 definitive %s pauses and closes without credit payload', async(status)=>{
  const e=env();await e.start();e.request.mockResolvedValueOnce({ok:false,status,json:async()=>({})});
  expect(await e.tracker.checkpoint()).toBe(false);expect(e.conflict).toHaveBeenCalledTimes(1);
  expect(await e.tracker.checkpoint()).toBe(false);expect(await e.tracker.end()).toBe(true);
  expect(e.request.mock.calls[2][1].body).toBe('{}');
});
test('T-WAT-001 does not backfill long app suspension',async()=>{
 const e=env();await e.start();e.tracker.sample(playing);e.at(60000);e.tracker.sample({...playing,positionMs:30000});await e.tracker.checkpoint();
 expect(JSON.parse(e.request.mock.calls[1][1].body).client_cumulative_active_ms).toBe(0);
});
