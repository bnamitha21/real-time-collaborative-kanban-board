import { create } from "zustand";
import { http, setToken } from "../api/http";
import type { Role } from "../lib/permissions";

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface TenantInfo {
  id: string;
  name: string;
  role: Role;
}

export interface WorkspaceItem {
  organization: {
    id: string;
    name: string;
  };
  role: Role;
  tenants: TenantInfo[];
}

export interface SessionState {
  user: User | null;
  workspaces: WorkspaceItem[];
  activeOrgId: string | null;
  activeTenantId: string | null;
  status: "idle" | "loading" | "authenticated" | "unauthenticated";
  requestEpoch: number;

  initSession: () => Promise<void>;
  login: (email: string, pass: string) => Promise<void>;
  logout: () => Promise<void>;
  switchOrg: (orgId: string) => void;
  switchTenant: (tenantId: string) => void;
  getActiveRole: () => Role | null;
  getActiveOrg: () => { id: string; name: string } | null;
  getActiveTenant: () => TenantInfo | null;
}

const STORAGE_KEY_ORG = "kanban:last_org";
const STORAGE_KEY_TENANT = "kanban:last_tenant";

export const useSessionStore = create<SessionState>((set, get) => ({
  user: null,
  workspaces: [],
  activeOrgId: null,
  activeTenantId: null,
  status: "idle",
  requestEpoch: 0,

  initSession: async () => {
    set({ status: "loading" });
    try {
      const refreshRes = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });

      if (!refreshRes.ok) {
        setToken(null);
        set({ user: null, workspaces: [], status: "unauthenticated" });
        return;
      }

      const refreshData = await refreshRes.json();
      const token = refreshData?.data?.accessToken;
      const user = refreshData?.data?.user;
      if (!token || !user) {
        setToken(null);
        set({ user: null, workspaces: [], status: "unauthenticated" });
        return;
      }

      setToken(token);

      const wsRes = await http.get<{ data: WorkspaceItem[] }>("/me/workspaces");
      const workspaces = wsRes.data || [];

      // Restore active org and tenant
      let activeOrgId = localStorage.getItem(STORAGE_KEY_ORG);
      let activeTenantId = localStorage.getItem(STORAGE_KEY_TENANT);

      let matchedOrg = workspaces.find((w) => w.organization.id === activeOrgId);
      if (!matchedOrg && workspaces.length > 0) {
        matchedOrg = workspaces[0];
        activeOrgId = matchedOrg.organization.id;
      }

      if (matchedOrg) {
        const matchedTenant = matchedOrg.tenants.find((t) => t.id === activeTenantId);
        if (matchedTenant) {
          activeTenantId = matchedTenant.id;
        } else if (matchedOrg.tenants.length > 0) {
          activeTenantId = matchedOrg.tenants[0].id;
        } else {
          activeTenantId = null;
        }
      } else {
        activeOrgId = null;
        activeTenantId = null;
      }

      if (activeOrgId) localStorage.setItem(STORAGE_KEY_ORG, activeOrgId);
      if (activeTenantId) localStorage.setItem(STORAGE_KEY_TENANT, activeTenantId);

      set({
        user,
        workspaces,
        activeOrgId,
        activeTenantId,
        status: "authenticated",
        requestEpoch: get().requestEpoch + 1,
      });
    } catch {
      setToken(null);
      set({ user: null, workspaces: [], status: "unauthenticated" });
    }
  },

  login: async (email: string, pass: string) => {
    set({ status: "loading" });
    const res = await http.post<{ data: { accessToken: string; user: User } }>(
      "/auth/login",
      { email, password: pass },
    );
    const token = res.data.accessToken;
    const user = res.data.user;
    setToken(token);

    const wsRes = await http.get<{ data: WorkspaceItem[] }>("/me/workspaces");
    const workspaces = wsRes.data || [];

    let activeOrgId = localStorage.getItem(STORAGE_KEY_ORG);
    let activeTenantId = localStorage.getItem(STORAGE_KEY_TENANT);

    let matchedOrg = workspaces.find((w) => w.organization.id === activeOrgId);
    if (!matchedOrg && workspaces.length > 0) {
      matchedOrg = workspaces[0];
      activeOrgId = matchedOrg.organization.id;
    }

    if (matchedOrg) {
      const matchedTenant = matchedOrg.tenants.find((t) => t.id === activeTenantId);
      if (matchedTenant) {
        activeTenantId = matchedTenant.id;
      } else if (matchedOrg.tenants.length > 0) {
        activeTenantId = matchedOrg.tenants[0].id;
      } else {
        activeTenantId = null;
      }
    } else {
      activeOrgId = null;
      activeTenantId = null;
    }

    if (activeOrgId) localStorage.setItem(STORAGE_KEY_ORG, activeOrgId);
    if (activeTenantId) localStorage.setItem(STORAGE_KEY_TENANT, activeTenantId);

    set({
      user,
      workspaces,
      activeOrgId,
      activeTenantId,
      status: "authenticated",
      requestEpoch: get().requestEpoch + 1,
    });
  },

  logout: async () => {
    try {
      await http.post("/auth/logout");
    } catch {
      // Ignore logout request errors
    } finally {
      setToken(null);
      set({
        user: null,
        workspaces: [],
        activeOrgId: null,
        activeTenantId: null,
        status: "unauthenticated",
        requestEpoch: get().requestEpoch + 1,
      });
    }
  },

  switchOrg: (orgId: string) => {
    const { workspaces, requestEpoch } = get();
    const org = workspaces.find((w) => w.organization.id === orgId);
    if (!org) return;

    const firstTenant = org.tenants[0]?.id || null;
    localStorage.setItem(STORAGE_KEY_ORG, orgId);
    if (firstTenant) {
      localStorage.setItem(STORAGE_KEY_TENANT, firstTenant);
    } else {
      localStorage.removeItem(STORAGE_KEY_TENANT);
    }

    set({
      activeOrgId: orgId,
      activeTenantId: firstTenant,
      requestEpoch: requestEpoch + 1,
    });
  },

  switchTenant: (tenantId: string) => {
    const { workspaces, activeOrgId, requestEpoch } = get();
    const currentOrg = workspaces.find((w) => w.organization.id === activeOrgId);
    if (!currentOrg) return;

    const tenant = currentOrg.tenants.find((t) => t.id === tenantId);
    if (!tenant) return;

    localStorage.setItem(STORAGE_KEY_TENANT, tenantId);
    set({
      activeTenantId: tenantId,
      requestEpoch: requestEpoch + 1,
    });
  },

  getActiveRole: () => {
    const { workspaces, activeOrgId, activeTenantId } = get();
    const currentOrg = workspaces.find((w) => w.organization.id === activeOrgId);
    if (!currentOrg) return null;

    if (currentOrg.role === "org_admin") {
      return "org_admin";
    }

    const tenant = currentOrg.tenants.find((t) => t.id === activeTenantId);
    return tenant ? tenant.role : null;
  },

  getActiveOrg: () => {
    const { workspaces, activeOrgId } = get();
    const currentOrg = workspaces.find((w) => w.organization.id === activeOrgId);
    return currentOrg ? currentOrg.organization : null;
  },

  getActiveTenant: () => {
    const { workspaces, activeOrgId, activeTenantId } = get();
    const currentOrg = workspaces.find((w) => w.organization.id === activeOrgId);
    if (!currentOrg) return null;
    return currentOrg.tenants.find((t) => t.id === activeTenantId) || null;
  },
}));
