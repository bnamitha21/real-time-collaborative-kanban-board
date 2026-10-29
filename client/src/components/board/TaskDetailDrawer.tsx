import { useState, useEffect, useRef } from "react";
import styles from "./TaskDetailDrawer.module.css";
import { Drawer, Button, Select, Dialog } from "../ui";
import { TrashIcon } from "../icons";
import type { TaskDto, ColumnDto } from "../../store/board";
import type { Role } from "../../lib/permissions";

export interface BranchMember {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface TaskDetailDrawerProps {
  task: TaskDto | null;
  columns: ColumnDto[];
  members: BranchMember[];
  isOpen: boolean;
  currentUserRole: Role | null;
  currentUserId: string | null;
  onClose: () => void;
  onSave: (
    taskId: string,
    updates: {
      title: string;
      description: string;
      assigneeId: string | null;
      priority: "low" | "medium" | "high";
      columnId: string;
      expectedVersion: number;
    },
  ) => Promise<void>;
  onDelete?: (taskId: string) => Promise<void>;
}

export function TaskDetailDrawer({
  task,
  columns,
  members,
  isOpen,
  currentUserRole,
  currentUserId,
  onClose,
  onSave,
  onDelete,
}: TaskDetailDrawerProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [assigneeId, setAssigneeId] = useState<string | null>(null);
  const [priority, setPriority] = useState<"low" | "medium" | "high">("medium");
  const [columnId, setColumnId] = useState("");
  const [expectedVersion, setExpectedVersion] = useState(1);
  const [isSaving, setIsSaving] = useState(false);
  const [conflictNotice, setConflictNotice] = useState<string | null>(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Baseline snapshot for tracking user edits
  const baselineRef = useRef<{
    title: string;
    description: string;
    assigneeId: string | null;
    priority: "low" | "medium" | "high";
    columnId: string;
  }>({
    title: "",
    description: "",
    assigneeId: null,
    priority: "medium",
    columnId: "",
  });

  const isDirty =
    Boolean(task) &&
    (title !== baselineRef.current.title ||
      description !== baselineRef.current.description ||
      assigneeId !== baselineRef.current.assigneeId ||
      priority !== baselineRef.current.priority ||
      columnId !== baselineRef.current.columnId);

  // Permission checks
  const isAssignee = task?.assigneeId === currentUserId;
  const isAdmin = currentUserRole === "org_admin" || currentUserRole === "tenant_admin";
  const canEditTitleDesc = isAdmin || isAssignee;
  const canChangeAssignee = isAdmin;
  const canChangeStatus = isAdmin || isAssignee;
  const canChangePriority = isAdmin || isAssignee;
  const canDelete = isAdmin;

  const syncBaseline = (t: TaskDto) => {
    setTitle(t.title);
    setDescription(t.description);
    setAssigneeId(t.assigneeId);
    setPriority(t.priority);
    setColumnId(t.columnId);
    setExpectedVersion(t.version);
    baselineRef.current = {
      title: t.title,
      description: t.description,
      assigneeId: t.assigneeId,
      priority: t.priority,
      columnId: t.columnId,
    };
  };

  // Sync state when task is opened or changes
  useEffect(() => {
    if (!task) return;

    if (!isOpen) {
      syncBaseline(task);
      setConflictNotice(null);
      return;
    }

    // Task version changed while open
    if (task.version > expectedVersion) {
      if (!isDirty) {
        // Silent sync
        syncBaseline(task);
      } else {
        // Dirty-form concurrent update: preserve edits and warn
        setConflictNotice(
          "This task was updated on the server. Review the changes before saving.",
        );
      }
    }
  }, [task, isOpen, expectedVersion, isDirty]);

  // Reset fields when new task ID is opened
  useEffect(() => {
    if (task && isOpen) {
      syncBaseline(task);
      setConflictNotice(null);
    }
  }, [task?.id, isOpen]);

  const handleShowLatest = () => {
    if (!task) return;
    syncBaseline(task);
    setConflictNotice(null);
  };

  const handleDiscard = () => {
    if (!task) return;
    syncBaseline(task);
    setConflictNotice(null);
  };

  const handleSave = async () => {
    if (!task || !title.trim() || isSaving) return;
    setIsSaving(true);
    try {
      await onSave(task.id, {
        title: title.trim(),
        description: description.trim(),
        assigneeId,
        priority,
        columnId,
        expectedVersion,
      });
      setConflictNotice(null);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!task || !onDelete || isDeleting) return;
    setIsDeleting(true);
    try {
      await onDelete(task.id);
      setDeleteConfirmOpen(false);
      onClose();
    } finally {
      setIsDeleting(false);
    }
  };

  if (!task && isOpen) {
    return (
      <Drawer open={isOpen} title="Task" onClose={onClose}>
        <div className={styles.deletedBanner}>
          <span>This task was deleted.</span>
          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </Drawer>
    );
  }

  if (!task) return null;

  const currentColumn = columns.find((c) => c.id === (isDirty ? columnId : task.columnId));
  const assignedMember = members.find((m) => m.id === (isDirty ? assigneeId : task.assigneeId));

  const drawerFooter = isDirty ? (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={handleDiscard}
        disabled={isSaving}
      >
        Discard
      </Button>
      <Button
        variant="primary"
        size="sm"
        onClick={handleSave}
        disabled={isSaving || !title.trim()}
      >
        {isSaving ? "Saving…" : "Save"}
      </Button>
    </>
  ) : null;

  const drawerActions = canDelete && onDelete ? (
    <Button
      variant="ghost"
      size="sm"
      iconOnly
      onClick={() => setDeleteConfirmOpen(true)}
      title="Delete task"
      aria-label="Delete task"
    >
      <TrashIcon size={16} />
    </Button>
  ) : null;

  return (
    <>
      <Drawer
        open={isOpen}
        title={canEditTitleDesc ? "Edit Task" : "Task Details"}
        onClose={onClose}
        footer={drawerFooter}
        actions={drawerActions}
      >
        <div className={styles.container}>
          {conflictNotice && (
            <div className={styles.noticeBanner} role="alert">
              <span>{conflictNotice}</span>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleShowLatest}
              >
                Show latest
              </Button>
            </div>
          )}

          {/* Title */}
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Title</label>
            {canEditTitleDesc ? (
              <input
                type="text"
                className={styles.titleInput}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Task title"
                required
              />
            ) : (
              <div className={styles.readOnlyValue}>{task.title}</div>
            )}
          </div>

          {/* Description */}
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Description</label>
            {canEditTitleDesc ? (
              <textarea
                className={styles.textarea}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Add more details about this task…"
                rows={4}
              />
            ) : (
              <div className={styles.readOnlyValue}>
                {task.description || "No description provided."}
              </div>
            )}
          </div>

          {/* Status Column */}
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Status</label>
            {canChangeStatus ? (
              <Select
                value={columnId}
                onChange={(e) => setColumnId(e.target.value)}
              >
                {columns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </Select>
            ) : (
              <div className={styles.readOnlyValue}>
                {currentColumn?.name || task.columnId}
              </div>
            )}
          </div>

          {/* Assignee */}
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Assigned member</label>
            {canChangeAssignee ? (
              <Select
                value={assigneeId || ""}
                onChange={(e) => setAssigneeId(e.target.value || null)}
              >
                <option value="">Unassigned</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} ({m.email})
                  </option>
                ))}
              </Select>
            ) : (
              <div className={styles.readOnlyValue}>
                {assignedMember ? assignedMember.name : "Unassigned"}
              </div>
            )}
          </div>

          {/* Priority */}
          <div className={styles.fieldGroup}>
            <label className={styles.label}>Priority</label>
            {canChangePriority ? (
              <Select
                value={priority}
                onChange={(e) =>
                  setPriority(e.target.value as "low" | "medium" | "high")
                }
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </Select>
            ) : (
              <div className={styles.readOnlyValue}>
                {task.priority.toUpperCase()}
              </div>
            )}
          </div>

          {/* Read-only metadata */}
          <div className={styles.metaSection}>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Version</span>
              <span className={styles.metaValue}>v{task.version}</span>
            </div>
            <div className={styles.metaItem}>
              <span className={styles.metaLabel}>Task ID</span>
              <span className={styles.metaValue}>
                {task.id.slice(0, 8)}…
              </span>
            </div>
            {task.createdAt && (
              <div className={styles.metaItem}>
                <span className={styles.metaLabel}>Created</span>
                <span className={styles.metaValue}>
                  {new Date(task.createdAt).toLocaleString()}
                </span>
              </div>
            )}
            {task.updatedAt && (
              <div className={styles.metaItem}>
                <span className={styles.metaLabel}>Updated</span>
                <span className={styles.metaValue}>
                  {new Date(task.updatedAt).toLocaleString()}
                </span>
              </div>
            )}
          </div>
        </div>
      </Drawer>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        title="Delete Task"
        onClose={() => setDeleteConfirmOpen(false)}
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setDeleteConfirmOpen(false)}
              disabled={isDeleting}
            >
              Cancel
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting…" : "Delete"}
            </Button>
          </>
        }
      >
        <p>
          Are you sure you want to permanently delete{" "}
          <strong>"{task.title}"</strong>? This action cannot be undone.
        </p>
      </Dialog>
    </>
  );
}
