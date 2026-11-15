// Run: node --experimental-strip-types tests/mediaSupport.test.ts   (no extra dependencies)
// Camera/microphone rules for Android Chrome and iOS Safari. These check the logic only; the real camera, permission
// prompts and the video to the supervisor must still be tried on real phones (see frontend/README.md).
import assert from "node:assert/strict";
import { test } from "node:test";
import { broadcastText, CAMERA, cameraWorking, captureAttempts, detectPlatform, frameAdvanced, isInAppBrowser, mediaErrorText, retryWithSimplerRequest, insecurePageHint, mediaServerProblem } from "../src/mediaSupport.ts";

const UA = {
  androidChrome: "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36",
  iphoneSafari: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  ipadOs: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  macSafari: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  windowsChrome: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  instagramIos: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 340.0.0.22.109",
  androidWebView: "Mozilla/5.0 (Linux; Android 14; SM-A546E; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/131.0.6778.135 Mobile Safari/537.36",
};

test("platform: Android Chrome, iPhone Safari, iPadOS (reports a Mac) and desktop", () => {
  assert.equal(detectPlatform(UA.androidChrome, 5), "android");
  assert.equal(detectPlatform(UA.iphoneSafari, 5), "ios");
  assert.equal(detectPlatform(UA.ipadOs, 5), "ios");          // iPad: Mac user agent, but a touch screen
  assert.equal(detectPlatform(UA.macSafari, 0), "desktop");
  assert.equal(detectPlatform(UA.windowsChrome, 0), "desktop");
});

test("in-app browsers (no reliable camera) are recognised; Chrome and Safari are not", () => {
  assert.equal(isInAppBrowser(UA.instagramIos), true);
  assert.equal(isInAppBrowser(UA.androidWebView), true);
  assert.equal(isInAppBrowser(UA.androidChrome), false);
  assert.equal(isInAppBrowser(UA.iphoneSafari), false);
});

test("camera request: front camera first, then simpler requests, the last one without microphone", () => {
  assert.deepEqual(CAMERA.facingMode, { ideal: "user" });     // ideal, not exact: a phone without a front camera still works
  const a = captureAttempts();
  assert.equal(a.length, 3);
  assert.deepEqual((a[0].video as MediaTrackConstraints).facingMode, { ideal: "user" });
  assert.equal(a[0].audio, true);
  assert.equal((a[1].video as MediaTrackConstraints).width, undefined);   // no size: older cameras accept it
  assert.equal(a[2].audio, false);                                          // camera only when the mic cannot open
});

test("a refused permission is not asked again; a busy, missing or over-constrained device is", () => {
  for (const n of ["NotAllowedError", "SecurityError", "TypeError", "UnsupportedError", undefined]) assert.equal(retryWithSimplerRequest(n), false, String(n));
  for (const n of ["OverconstrainedError", "NotFoundError", "NotReadableError", "AbortError"]) assert.equal(retryWithSimplerRequest(n), true, n);
});

test("permission refused: steps for the student's own phone", () => {
  const android = mediaErrorText("NotAllowedError", true, "android");
  const ios = mediaErrorText("NotAllowedError", true, "ios");
  assert.match(android, /ditolak/);
  assert.match(android, /Chrome Android/);
  assert.match(ios, /Safari/);
  assert.match(ios, /Pengaturan Situs Web/);
  assert.notEqual(android, ios);
  for (const t of [android, ios]) assert.match(t, /Coba lagi/);     // the page has a "Coba lagi" button
});

test("no camera, camera used by another app, unsupported browser, not HTTPS", () => {
  assert.match(mediaErrorText("NotFoundError", true, "android"), /tidak ditemukan/);
  assert.match(mediaErrorText("NotReadableError", true, "ios"), /dipakai aplikasi lain/);
  assert.match(mediaErrorText("AbortError", true, "android"), /dipakai aplikasi lain/);
  assert.match(mediaErrorText("UnsupportedError", true, "android"), /Chrome \(Android\) atau Safari \(iPhone\)/);
  assert.match(mediaErrorText("UnsupportedError", true, "ios", true), /di dalam aplikasi/);
  // Not a secure page: always the HTTPS message, whatever the error (phones over http://<ip> never get a camera).
  assert.match(mediaErrorText("NotAllowedError", false, "android"), /HTTPS/);
  assert.match(mediaErrorText(undefined, true, "desktop"), /Coba lagi/);
});

test("a camera counts as working only when its picture moves", () => {
  assert.equal(frameAdvanced(1.0, 2.5, 4, 640), true);
  assert.equal(frameAdvanced(2.5, 2.5, 4, 640), false);     // frozen (iOS in the background, camera taken over)
  assert.equal(frameAdvanced(-1, 0.2, 1, 640), false);      // no decoded frame yet
  assert.equal(frameAdvanced(-1, 0.2, 4, 0), false);        // permission granted, but no picture
});

test("camera working = live, not muted, and new frames (iOS mutes the track in the background)", () => {
  assert.equal(cameraWorking({ readyState: "live", muted: false }, true), true);
  assert.equal(cameraWorking({ readyState: "live", muted: false }, false), false);   // frozen picture
  assert.equal(cameraWorking({ readyState: "live", muted: true }, true), false);     // iOS: Safari in the background
  assert.equal(cameraWorking({ readyState: "ended", muted: false }, true), false);   // taken by another app / stopped
  assert.equal(cameraWorking(undefined, true), false);                               // no camera track at all
});

test("broadcast status: 'received' only after somebody subscribed to the camera", () => {
  assert.equal(broadcastText("off"), "");
  assert.match(broadcastText("connecting"), /Menyambungkan/);
  assert.match(broadcastText("reconnecting"), /Menyambung ulang/);
  assert.match(broadcastText("sending"), /menunggu pengawas/);
  assert.match(broadcastText("received"), /sudah diterima/);
});

test("front or back camera: the chosen side is asked for in every attempt, front by default", () => {
  assert.deepEqual(captureAttempts().map((c) => JSON.stringify(c.video)).every((v) => v.includes('"user"')), true);
  const back = captureAttempts("environment");
  assert.ok(back.every((c) => JSON.stringify(c.video).includes('"environment"') && !JSON.stringify(c.video).includes('"user"')));
  assert.equal(back[2].audio, false);                                     // still a camera when the microphone fails
});

test("camera needs a secure page: https or localhost; a phone on http://<ip> is told why", () => {
  assert.equal(insecurePageHint(true, "https:", "ujian.sekolah.sch.id"), null);
  assert.equal(insecurePageHint(true, "http:", "localhost"), null);
  const hint = insecurePageHint(false, "http:", "192.168.1.10");
  assert.ok(hint && hint.includes("http://192.168.1.10") && hint.includes("https://"));
});

test("video server address seen from the student's device", () => {
  // localhost / 127.0.0.1 from a phone = the phone itself
  assert.match(mediaServerProblem("ws://localhost:7880", "ujian.sekolah.sch.id", "https:") ?? "", /perangkat ini sendiri/);
  assert.match(mediaServerProblem("ws://127.0.0.1:7880", "192.168.1.10", "http:") ?? "", /perangkat ini sendiri/);
  assert.equal(mediaServerProblem("ws://localhost:7880", "localhost", "http:"), null);          // computer that runs it
  // ws:// is blocked on an https page
  assert.match(mediaServerProblem("ws://192.168.1.10:7880", "ujian.sekolah.sch.id", "https:") ?? "", /wss:\/\//);
  assert.equal(mediaServerProblem("ws://192.168.1.10:7880", "192.168.1.10", "http:"), null);
  assert.equal(mediaServerProblem("wss://video.sekolah.sch.id", "ujian.sekolah.sch.id", "https:"), null);
  // Jitsi gives a bare domain
  assert.equal(mediaServerProblem("meet.sekolah.sch.id", "ujian.sekolah.sch.id", "https:"), null);
  assert.match(mediaServerProblem("localhost:8443", "ujian.sekolah.sch.id", "https:") ?? "", /localhost/);
});
