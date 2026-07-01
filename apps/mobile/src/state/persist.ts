import * as SecureStore from "expo-secure-store";
import { createJSONStorage, type StateStorage } from "zustand/middleware";

/**
 * SecureStore-backed storage adapter for zustand's `persist` middleware.
 *
 * Keys must contain only alphanumeric characters, ".", "-" and "_", so all
 * persisted stores use the `stail_*` naming convention.
 */
const secureStorage: StateStorage = {
  getItem: (name) => SecureStore.getItemAsync(name),
  setItem: (name, value) => SecureStore.setItemAsync(name, value),
  removeItem: (name) => SecureStore.deleteItemAsync(name),
};

export const persistedStorage = createJSONStorage(() => secureStorage);
