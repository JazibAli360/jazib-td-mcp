// TD window lookup for td_window_capture (pure parts, tested offline).
export const WINDOWS_JXA = 'ObjC.import("CoreGraphics"); const l = ObjC.deepUnwrap(ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionAll, 0))); JSON.stringify(l.filter(w => (w.kCGWindowOwnerName || "").includes("TouchDesigner")).map(w => ({ id: w.kCGWindowNumber, layer: w.kCGWindowLayer, title: w.kCGWindowName || "", w: w.kCGWindowBounds.Width, h: w.kCGWindowBounds.Height })))';
export function pickWindow(wins, match) {
  const named = wins.filter((w) => w.title && w.w > 100 && w.h > 60);
  if (match) return named.find((w) => w.title.toLowerCase().includes(String(match).toLowerCase())) || null;
  return named.find((w) => w.title.startsWith('TouchDesigner ')) || named[0] || null;
}
