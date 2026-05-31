import type { UserRole } from "@/types/domain";

const CUSTOMER_SELF_ROUTE_PREFIXES = ["/me/"];
const CUSTOMER_FLOW_ROUTE_PREFIXES = ["/checkout/", "/payment/"];
const ADMIN_ROUTE_PREFIXES = ["/admin"];

export function isLocalAppPath(path: string | null | undefined): path is string {
  if (!path) {
    return false;
  }
  return path.startsWith("/") && !path.startsWith("//") && !path.includes("://");
}

export function isCustomerSelfRoute(path: string): boolean {
  return CUSTOMER_SELF_ROUTE_PREFIXES.some((prefix) => path === prefix.slice(0, -1) || path.startsWith(prefix));
}

export function isAdminRoute(path: string): boolean {
  return ADMIN_ROUTE_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`));
}

export function getDefaultAuthenticatedRoute(role: UserRole): string {
  return role === "admin" ? "/admin" : "/profile";
}

export function resolvePostLoginRedirect(candidatePath: string | null | undefined, role: UserRole): string {
  if (!isLocalAppPath(candidatePath)) {
    return getDefaultAuthenticatedRoute(role);
  }

  if (role === "admin") {
    return isAdminRoute(candidatePath) ? candidatePath : "/admin";
  }

  if (isAdminRoute(candidatePath)) {
    return "/profile";
  }

  if (
    candidatePath === "/profile" ||
    isCustomerSelfRoute(candidatePath) ||
    CUSTOMER_FLOW_ROUTE_PREFIXES.some((prefix) => candidatePath.startsWith(prefix))
  ) {
    return candidatePath;
  }

  return "/profile";
}
