// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from "vitest";

import { resolvePostLoginRedirect } from "@/shared/routeAccess";
import { STORAGE_KEYS } from "@/shared/constants";
import {
  clearAuthStorage,
  getRememberedProtectedRedirect,
  rememberProtectedRedirect,
  storeAuthTokens,
  storeRole,
} from "@/shared/storage";

describe("auth redirect route isolation", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("clears remembered customer self-service routes on logout before an admin login", () => {
    const customerOrderRoute = "/me/orders/order-123";

    storeAuthTokens({
      accessToken: "customer-access-token",
      refreshToken: "customer-refresh-token",
    });
    storeRole("user");
    rememberProtectedRedirect(customerOrderRoute);

    clearAuthStorage();

    expect(window.localStorage.getItem(STORAGE_KEYS.accessToken)).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEYS.refreshToken)).toBeNull();
    expect(window.localStorage.getItem(STORAGE_KEYS.userRole)).toBeNull();
    expect(getRememberedProtectedRedirect()).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEYS.lastProtectedRoute)).toBeNull();
    expect(resolvePostLoginRedirect(getRememberedProtectedRedirect(), "admin")).toBe("/admin");
  });

  it("does not restore a customer order route for an admin login", () => {
    const customerOrderRoute = "/me/orders/order-123";

    rememberProtectedRedirect(customerOrderRoute);

    expect(resolvePostLoginRedirect(customerOrderRoute, "admin")).toBe("/admin");
    expect(resolvePostLoginRedirect(getRememberedProtectedRedirect(), "admin")).toBe("/admin");
  });

  it("keeps a customer order route available for a customer login", () => {
    const customerOrderRoute = "/me/orders/order-123";

    expect(resolvePostLoginRedirect(customerOrderRoute, "user")).toBe(customerOrderRoute);
  });
});
