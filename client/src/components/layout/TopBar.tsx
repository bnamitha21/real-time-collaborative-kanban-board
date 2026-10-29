import { useState, useRef, useEffect } from "react";
import styles from "./TopBar.module.css";
import { Avatar, Badge } from "../ui";
import {
  BuildingIcon,
  BranchIcon,
  ChevronDownIcon,
  CheckIcon,
} from "../icons";
import { useSessionStore } from "../../store/session";
import type { Role } from "../../lib/permissions";

export function formatRole(role: Role | null | undefined): string {
  if (!role) return "";
  if (role === "org_admin") return "Org Admin";
  if (role === "tenant_admin") return "Tenant Admin";
  return "Member";
}

export function TopBar() {
  const {
    user,
    workspaces,
    activeOrgId,
    activeTenantId,
    switchOrg,
    switchTenant,
    getActiveRole,
    logout,
  } = useSessionStore();

  const [orgOpen, setOrgOpen] = useState(false);
  const [tenantOpen, setTenantOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  const orgRef = useRef<HTMLDivElement>(null);
  const tenantRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (orgRef.current && !orgRef.current.contains(target)) setOrgOpen(false);
      if (tenantRef.current && !tenantRef.current.contains(target)) setTenantOpen(false);
      if (userRef.current && !userRef.current.contains(target)) setUserMenuOpen(false);
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    if (next === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  };

  const currentOrg = workspaces.find((w) => w.organization.id === activeOrgId);
  const currentTenant = currentOrg?.tenants.find((t) => t.id === activeTenantId);
  const currentRole = getActiveRole();

  return (
    <header className={styles.topBar}>
      <div className={styles.leftSection}>
        <span className={styles.appTitle}>
          Real-Time Collaborative Kanban Board
        </span>

        <div className={styles.divider} />

        <div className={styles.switchers}>
          {/* Organization Selector */}
          {workspaces.length <= 1 ? (
            <span className={styles.plainTextOrg}>
              {currentOrg?.organization.name || "Workspace"}
            </span>
          ) : (
            <div className={styles.userMenuWrapper} ref={orgRef}>
              <button
                type="button"
                className={styles.selectButton}
                onClick={() => {
                  setOrgOpen(!orgOpen);
                  setTenantOpen(false);
                }}
                aria-haspopup="listbox"
                aria-expanded={orgOpen}
                aria-label="Select organization"
              >
                <BuildingIcon size={14} />
                <span>{currentOrg?.organization.name || "Select Org"}</span>
                <ChevronDownIcon size={12} />
              </button>

              {orgOpen && (
                <div
                  className={`${styles.dropdownMenu} ${styles.dropdownMenuLeft}`}
                  role="listbox"
                >
                  {workspaces.map((ws) => {
                    const isSelected = ws.organization.id === activeOrgId;
                    return (
                      <button
                        key={ws.organization.id}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        className={`${styles.menuItem} ${
                          isSelected ? styles.menuItemActive : ""
                        }`}
                        onClick={() => {
                          switchOrg(ws.organization.id);
                          setOrgOpen(false);
                        }}
                      >
                        <span>{ws.organization.name}</span>
                        {isSelected && <CheckIcon size={14} />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Branch Switcher */}
          {currentOrg && currentOrg.tenants.length > 0 && (
            <div className={styles.userMenuWrapper} ref={tenantRef}>
              <button
                type="button"
                className={styles.selectButton}
                onClick={() => {
                  setTenantOpen(!tenantOpen);
                  setOrgOpen(false);
                }}
                aria-haspopup="listbox"
                aria-expanded={tenantOpen}
                aria-label="Select branch"
              >
                <BranchIcon size={14} />
                <span>{currentTenant?.name || "Select Branch"}</span>
                {currentRole && (
                  <Badge variant="default">{formatRole(currentRole)}</Badge>
                )}
                <ChevronDownIcon size={12} />
              </button>

              {tenantOpen && (
                <div
                  className={`${styles.dropdownMenu} ${styles.dropdownMenuLeft}`}
                  role="listbox"
                >
                  {currentOrg.tenants.map((t) => {
                    const isSelected = t.id === activeTenantId;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        role="option"
                        aria-selected={isSelected}
                        className={`${styles.menuItem} ${
                          isSelected ? styles.menuItemActive : ""
                        }`}
                        onClick={() => {
                          switchTenant(t.id);
                          setTenantOpen(false);
                        }}
                      >
                        <div>
                          <div>{t.name}</div>
                          <span className={styles.roleTag}>
                            {formatRole(t.role)}
                          </span>
                        </div>
                        {isSelected && <CheckIcon size={14} />}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className={styles.rightSection}>
        {/* Status indicator */}
        <div className={styles.statusIndicator} title="Connected to server">
          <span className={styles.statusDot} />
          <span>Live</span>
        </div>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          className={styles.themeToggle}
          title={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
          aria-label="Toggle theme"
        >
          {theme === "light" ? "🌙" : "☀️"}
        </button>

        {/* User Menu */}
        {user && (
          <div className={styles.userMenuWrapper} ref={userRef}>
            <button
              type="button"
              className={styles.userButton}
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              aria-haspopup="menu"
              aria-expanded={userMenuOpen}
              aria-label="User account menu"
            >
              <Avatar name={user.name} id={user.id} size="sm" />
              <span>{user.name}</span>
              <ChevronDownIcon size={12} />
            </button>

            {userMenuOpen && (
              <div className={styles.dropdownMenu} role="menu">
                <div className={styles.menuHeader}>
                  <div className={styles.menuUserName}>{user.name}</div>
                  <div className={styles.menuUserEmail}>{user.email}</div>
                  {currentRole && (
                    <Badge variant="primary" className={styles.roleTag}>
                      {formatRole(currentRole)}
                    </Badge>
                  )}
                </div>

                <button
                  type="button"
                  className={styles.menuItem}
                  onClick={() => {
                    setUserMenuOpen(false);
                    logout();
                  }}
                  role="menuitem"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
