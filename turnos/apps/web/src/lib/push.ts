"use client";

import { api, unwrap } from "./api/client";

export type PushState = "unsupported" | "ios-install" | "server-off" | "denied" | "off" | "on";

const isIos = () => /iPad|iPhone|iPod/.test(navigator.userAgent);
const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;

function b64ToBytes(b64url: string): Uint8Array<ArrayBuffer> {
  const pad = "=".repeat((4 - (b64url.length % 4)) % 4);
  const raw = atob((b64url + pad).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

async function config(): Promise<{ enabled: boolean; publicKey: string | null }> {
  return unwrap(api.GET("/api/v1/push/config") as never);
}

export async function pushState(): Promise<PushState> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return isIos() && !isStandalone() ? "ios-install" : "unsupported";
  }
  if (!(await config()).enabled) return "server-off";
  if (Notification.permission === "denied") return "denied";
  const reg = await navigator.serviceWorker.getRegistration("/sw.js");
  const sub = await reg?.pushManager.getSubscription();
  return sub ? "on" : "off";
}

export async function enablePush(): Promise<PushState> {
  const cfg = await config();
  if (!cfg.enabled || !cfg.publicKey) return "server-off";
  const permission = await Notification.requestPermission();
  if (permission !== "granted") return permission === "denied" ? "denied" : "off";
  const reg = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(cfg.publicKey) });
  const json = sub.toJSON() as { endpoint: string; keys: { p256dh: string; auth: string } };
  await unwrap(api.POST("/api/v1/push/subscriptions", { body: { endpoint: json.endpoint, keys: json.keys } }) as never);
  return "on";
}

export async function disablePush(): Promise<PushState> {
  const reg = await navigator.serviceWorker.getRegistration("/sw.js");
  const sub = await reg?.pushManager.getSubscription();
  if (sub) {
    await unwrap(api.DELETE("/api/v1/push/subscriptions", { body: { endpoint: sub.endpoint } }) as never).catch(() => undefined);
    await sub.unsubscribe();
  }
  return "off";
}
