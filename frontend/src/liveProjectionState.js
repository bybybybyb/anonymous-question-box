export const LIVE_PROJECTION_STATE_KEY = "aqbox_live_projection_state";
export const FONT_SIZES = ["fs-6", "fs-5", "fs-4", "fs-3", "fs-2", "fs-1"];
export const DEFAULT_FONT_SIZE_IDX = 1;

const localEventName = "aqbox-live-projection-state";

function getWindow() {
  if (typeof window === "undefined") {
    return null;
  }
  return window;
}

function getStorage() {
  const currentWindow = getWindow();
  if (!currentWindow) {
    return null;
  }

  try {
    return currentWindow.localStorage;
  } catch {
    return null;
  }
}

function normalizeImages(images) {
  return Array.isArray(images) ? images : [];
}

function normalizeFontSizeIdx(fontSizeIdx) {
  return Number.isInteger(fontSizeIdx) ? fontSizeIdx : DEFAULT_FONT_SIZE_IDX;
}

function normalizeUpdatedAt(updatedAt) {
  return typeof updatedAt === "string" ? updatedAt : new Date().toISOString();
}

function normalizeState(state) {
  if (!state || typeof state !== "object") {
    return null;
  }

  return {
    owner: typeof state.owner === "string" ? state.owner : "",
    sessionId: typeof state.sessionId === "string" ? state.sessionId : "",
    text: typeof state.text === "string" ? state.text : "",
    images: normalizeImages(state.images),
    fontSizeIdx: normalizeFontSizeIdx(state.fontSizeIdx),
    updatedAt: normalizeUpdatedAt(state.updatedAt),
  };
}

function dispatchLocalChange(state) {
  const currentWindow = getWindow();
  if (!currentWindow || typeof currentWindow.CustomEvent !== "function") {
    return;
  }

  currentWindow.dispatchEvent(
    new currentWindow.CustomEvent(localEventName, {
      detail: state,
    })
  );
}

export function readProjectionState() {
  const storage = getStorage();
  if (!storage) {
    return null;
  }

  let rawState;
  try {
    rawState = storage.getItem(LIVE_PROJECTION_STATE_KEY);
  } catch {
    return null;
  }

  if (!rawState) {
    return null;
  }

  try {
    return normalizeState(JSON.parse(rawState));
  } catch {
    return null;
  }
}

export function writeProjectionState(state) {
  const normalizedState = normalizeState({
    ...state,
    updatedAt: state?.updatedAt || new Date().toISOString(),
  });

  if (!normalizedState) {
    return null;
  }

  const storage = getStorage();
  if (!storage) {
    return normalizedState;
  }

  try {
    storage.setItem(
      LIVE_PROJECTION_STATE_KEY,
      JSON.stringify(normalizedState)
    );
  } catch {
    return normalizedState;
  }

  dispatchLocalChange(normalizedState);
  return normalizedState;
}

export function clearProjectionState() {
  const storage = getStorage();
  if (storage) {
    try {
      storage.removeItem(LIVE_PROJECTION_STATE_KEY);
    } catch {
      // Ignore unavailable storage.
    }
  }

  dispatchLocalChange(null);
}

export function subscribeProjectionState(callback) {
  const currentWindow = getWindow();
  if (!currentWindow || typeof callback !== "function") {
    return () => {};
  }

  const onStorage = (event) => {
    if (event.key !== LIVE_PROJECTION_STATE_KEY) {
      return;
    }
    callback(readProjectionState());
  };

  const onLocalChange = (event) => {
    callback(event.detail || null);
  };

  currentWindow.addEventListener("storage", onStorage);
  currentWindow.addEventListener(localEventName, onLocalChange);

  return () => {
    currentWindow.removeEventListener("storage", onStorage);
    currentWindow.removeEventListener(localEventName, onLocalChange);
  };
}

export const read = readProjectionState;
export const write = writeProjectionState;
export const clear = clearProjectionState;
export const subscribe = subscribeProjectionState;
