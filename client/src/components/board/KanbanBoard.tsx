import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from "@dnd-kit/core";
import { arrayMove, sortableKeyboardCoordinates } from "@dnd-kit/sortable";
import styles from "./KanbanBoard.module.css";
import { Column } from "./Column";
import { TaskCard } from "./TaskCard";
import { TaskDetailDrawer, type BranchMember } from "./TaskDetailDrawer";
import { Button, Spinner, Dialog, TextField, Toast } from "../ui";
import { PlusIcon } from "../icons";
import { http } from "../../api/http";
import { useBoardStore, type TaskDto, type ColumnDto } from "../../store/board";
import { useSessionStore } from "../../store/session";
import { useHistoryStore } from "../../store/history";
import { useActivityStore } from "../../store/activity";
import { moveTask } from "../../store/actions";
import { subscribeBoard, unsubscribeBoard } from "../../realtime/socket";
import { useConnectionStore } from "../../realtime/connection";
import { can } from "../../lib/permissions";

export interface BoardSummary {
  id: string;
  name: string;
}

export function KanbanBoard() {
  const { user, activeTenantId, getActiveRole, requestEpoch } = useSessionStore();
  const connectionStatus = useConnectionStore((s) => s.status);
  const {
    columns,
    tasks,
    order,
    loading,
    load,
    applyServerTask,
    removeTask,
    clear,
    setLoading,
  } = useBoardStore();

  const [boards, setBoards] = useState<BoardSummary[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<string | null>(null);
  const [members, setMembers] = useState<BranchMember[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [detailTask, setDetailTask] = useState<TaskDto | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // New board modal state
  const [isNewBoardOpen, setIsNewBoardOpen] = useState(false);
  const [newBoardName, setNewBoardName] = useState("");
  const [isCreatingBoard, setIsCreatingBoard] = useState(false);

  const currentRole = getActiveRole();
  const canCreateBoard = can(currentRole, "board:create");
  const canCreateTask = can(currentRole, "task:create");
  const canDeleteTask = can(currentRole, "task:delete");

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 6,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 150,
        tolerance: 5,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  // Map of userId -> name for display on cards
  const usersMap = useMemo(() => {
    const map: Record<string, string> = {};
    if (user) map[user.id] = user.name;
    for (const m of members) {
      map[m.id] = m.name;
    }
    return map;
  }, [user, members]);

  // Load boards and members for the active branch
  const fetchBranchData = useCallback(
    async (epochAtStart: number) => {
      // Clear undo history & activity when switching branch (Phase 9.5 & 13.1)
      useHistoryStore.getState().clear();
      useActivityStore.getState().clear();

      if (!activeTenantId) {
        clear();
        setBoards([]);
        return;
      }

      setLoading(true);
      try {
        const [boardsRes, membersRes] = await Promise.all([
          http.get<{ data: BoardSummary[] }>(`/tenants/${activeTenantId}/boards`),
          http
            .get<{ data: BranchMember[] }>(`/tenants/${activeTenantId}/members`)
            .catch(() => ({ data: [] })),
        ]);

        // Guard against race conditions if branch changed
        if (epochAtStart !== useSessionStore.getState().requestEpoch) {
          return;
        }

        const branchBoards = boardsRes.data || [];
        setBoards(branchBoards);
        setMembers(membersRes.data || []);

        if (branchBoards.length > 0) {
          // Select first board
          setSelectedBoardId(branchBoards[0].id);
        } else {
          setSelectedBoardId(null);
          clear();
        }
      } catch {
        setBoards([]);
        clear();
      } finally {
        setLoading(false);
      }
    },
    [activeTenantId, clear, setLoading],
  );

  useEffect(() => {
    fetchBranchData(requestEpoch);
  }, [fetchBranchData, requestEpoch]);

  // Load board snapshot when selectedBoardId changes
  const fetchBoardSnapshot = useCallback(
    async (bId: string) => {
      if (!activeTenantId || !bId) return;

      // Capture current epoch synchronously — before any await
      const epochAtStart = useSessionStore.getState().requestEpoch;

      // Clear stale board data before loading new snapshot
      clear();
      setLoading(true);
      try {
        const res = await http.get<{
          data: {
            board: BoardSummary;
            columns: ColumnDto[];
            tasks: TaskDto[];
          };
        }>(`/boards/${bId}`);

        // Guard: abort if tenant/org switched while we were fetching
        if (epochAtStart !== useSessionStore.getState().requestEpoch) {
          return;
        }

        load({
          boardId: bId,
          columns: res.data.columns || [],
          tasks: res.data.tasks || [],
        });
      } catch {
        clear();
      } finally {
        setLoading(false);
      }
    },
    [activeTenantId, load, clear, setLoading],
  );

  useEffect(() => {
    if (selectedBoardId) {
      subscribeBoard(selectedBoardId);
      fetchBoardSnapshot(selectedBoardId);
      return () => {
        unsubscribeBoard(selectedBoardId);
      };
    }
  }, [selectedBoardId, fetchBoardSnapshot]);

  // Handle task click to open detail drawer
  const handleTaskClick = (task: TaskDto) => {
    setDetailTask(task);
    setIsDetailOpen(true);
  };

  // Create new task in To Do column
  const handleCreateTask = async (columnId: string, title: string) => {
    if (!activeTenantId || !selectedBoardId) return;

    try {
      const res = await http.post<{ data: TaskDto }>(
        `/boards/${selectedBoardId}/tasks`,
        {
          columnId,
          title,
          priority: "medium",
          actionId: crypto.randomUUID(),
        },
      );
      applyServerTask(res.data);
      setToastMessage(`Created task "${title}"`);
    } catch {
      setToastMessage("Failed to create task");
    }
  };

  // Create new board
  const handleCreateBoard = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeTenantId || !newBoardName.trim() || isCreatingBoard) return;

    setIsCreatingBoard(true);
    try {
      const res = await http.post<{ data: BoardSummary }>(
        `/tenants/${activeTenantId}/boards`,
        { name: newBoardName.trim() },
      );
      setBoards((prev) => [...prev, res.data]);
      setSelectedBoardId(res.data.id);
      setIsNewBoardOpen(false);
      setNewBoardName("");
      setToastMessage(`Created board "${res.data.name}"`);
    } catch {
      setToastMessage("Failed to create board");
    } finally {
      setIsCreatingBoard(false);
    }
  };

  // Quick move via context menu
  const handleQuickMove = async (task: TaskDto, toColumnId: string) => {
    const res = await moveTask(task.id, toColumnId, null);
    if (res.conflict) {
      setToastMessage("This task was changed by another user. Showing the latest version.");
    } else if (!res.success) {
      setToastMessage(res.error || "Move failed");
    } else {
      const toCol = columns.find((c) => c.id === toColumnId);
      setToastMessage(`Moved "${task.title}" to ${toCol?.name || "column"}`);
    }
  };

  // Save task details from drawer
  const handleSaveTaskDetail = async (
    taskId: string,
    updates: {
      title: string;
      description: string;
      assigneeId: string | null;
      priority: "low" | "medium" | "high";
      columnId: string;
      expectedVersion: number;
    },
  ) => {
    if (!activeTenantId) return;

    try {
      // If column changed, perform move first
      if (detailTask && updates.columnId !== detailTask.columnId) {
        await http.post(`/tasks/${taskId}/move`, {
          toColumnId: updates.columnId,
          afterTaskId: null,
          expectedVersion: updates.expectedVersion,
        });
      }

      // Perform task update patch
      const res = await http.patch<{ data: TaskDto }>(`/tasks/${taskId}`, {
        title: updates.title,
        description: updates.description,
        assigneeId: updates.assigneeId,
        priority: updates.priority,
        expectedVersion: updates.expectedVersion,
      });

      applyServerTask(res.data);
      setDetailTask(res.data);
      setToastMessage("Task saved successfully");
    } catch {
      setToastMessage("Failed to save task: concurrent change detected");
      if (selectedBoardId) fetchBoardSnapshot(selectedBoardId);
    }
  };

  // Delete task
  const handleDeleteTask = async (taskOrId: string | TaskDto) => {
    const taskId = typeof taskOrId === "string" ? taskOrId : taskOrId.id;
    try {
      await http.del(`/tasks/${taskId}`);
      removeTask(taskId);
      setIsDetailOpen(false);
      setToastMessage("Task deleted");
    } catch {
      setToastMessage("Failed to delete task");
    }
  };

  // Drag and drop handlers
  const handleDragStart = (e: DragStartEvent) => {
    const id = String(e.active.id);
    setActiveTaskId(id);
  };

  const handleDragOver = (e: DragOverEvent) => {
    const { active, over } = e;
    if (!over) return;

    const aId = String(active.id);
    const oId = String(over.id);

    const activeTask = tasks[aId];
    if (!activeTask) return;

    // Check if over a column or over another card
    let overColId: string | null = null;
    if (columns.some((c) => c.id === oId)) {
      overColId = oId;
    } else if (tasks[oId]) {
      overColId = tasks[oId].columnId;
    }

    if (overColId && overColId !== activeTask.columnId) {
      // Optimistically move card across columns in local order
      const fromColId = activeTask.columnId;
      const fromOrder = [...(order[fromColId] || [])].filter((id) => id !== aId);
      const toOrder = [...(order[overColId] || [])];

      const overIndex = toOrder.indexOf(oId);
      if (overIndex >= 0) {
        toOrder.splice(overIndex, 0, aId);
      } else {
        toOrder.push(aId);
      }

      useBoardStore.setState((state) => ({
        tasks: {
          ...state.tasks,
          [aId]: { ...activeTask, columnId: overColId as string },
        },
        order: {
          ...state.order,
          [fromColId]: fromOrder,
          [overColId as string]: toOrder,
        },
      }));
    }
  };

  const handleDragEnd = async (e: DragEndEvent) => {
    const { active, over } = e;
    setActiveTaskId(null);

    if (!over) {
      if (selectedBoardId) fetchBoardSnapshot(selectedBoardId);
      return;
    }

    const aId = String(active.id);
    const oId = String(over.id);
    const activeTask = tasks[aId];
    if (!activeTask) return;

    // Determine target column
    let toColumnId: string;
    if (columns.some((c) => c.id === oId)) {
      toColumnId = oId;
    } else if (tasks[oId]) {
      toColumnId = tasks[oId].columnId;
    } else {
      toColumnId = activeTask.columnId;
    }

    // Determine final order in target column
    const colOrder = [...(order[toColumnId] || [])];
    const currentIndex = colOrder.indexOf(aId);
    let targetIndex = colOrder.indexOf(oId);

    if (targetIndex === -1) {
      // Dropped on column container
      targetIndex = colOrder.length - 1;
    }

    let finalOrder = colOrder;
    if (currentIndex >= 0 && targetIndex >= 0 && currentIndex !== targetIndex) {
      finalOrder = arrayMove(colOrder, currentIndex, targetIndex);
    }

    // Compute afterTaskId
    const newIdx = finalOrder.indexOf(aId);
    const afterTaskId = newIdx > 0 ? finalOrder[newIdx - 1] : null;

    // Announce move for accessibility
    const targetCol = columns.find((c) => c.id === toColumnId);
    setAnnouncement(
      `${activeTask.title} moved to ${targetCol?.name || "column"}, position ${
        newIdx + 1
      } of ${finalOrder.length}`,
    );

    const res = await moveTask(aId, toColumnId, afterTaskId);
    if (res.conflict) {
      setToastMessage("This task was changed by another user. Showing the latest version.");
    } else if (!res.success) {
      setToastMessage(res.error || "Move failed");
    }
  };

  const activeTask = activeTaskId ? tasks[activeTaskId] : null;

  return (
    <div className={styles.boardWrapper}>
      {/* Offline banner (spec requirement) */}
      {connectionStatus === "offline" && (
        <div className={styles.offlineBanner} role="alert">
          <span>You are offline. Changes are pending and are not saved yet.</span>
        </div>
      )}

      {/* Polite live region for screen readers */}
      <div aria-live="polite" className={styles.srOnly}>
        {announcement}
      </div>

      {/* Board Top Header */}
      <div className={styles.boardHeader}>
        <div className={styles.headerLeft}>
          {boards.length > 0 && (
            <div className={styles.boardSelector}>
              <select
                className={styles.boardSelect}
                value={selectedBoardId || ""}
                onChange={(e) => setSelectedBoardId(e.target.value)}
                aria-label="Select board"
              >
                {boards.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className={styles.headerRight}>
          {canCreateBoard && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsNewBoardOpen(true)}
            >
              <PlusIcon size={14} />
              <span>New board</span>
            </Button>
          )}
        </div>
      </div>

      {/* Loading state */}
      {loading ? (
        <div className={styles.loadingContainer}>
          <Spinner size="md" />
          <span>Loading board…</span>
        </div>
      ) : boards.length === 0 ? (
        /* Empty branch state (9.7) */
        <div className={styles.emptyStateContainer}>
          <div className={styles.emptyCard}>
            <p className={styles.emptyText}>No boards in this branch yet.</p>
            {canCreateBoard ? (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsNewBoardOpen(true)}
              >
                <PlusIcon size={14} />
                <span>Create board</span>
              </Button>
            ) : (
              <p className={styles.emptyText}>
                Ask a Tenant Admin to create a board.
              </p>
            )}
          </div>
        </div>
      ) : (
        /* Kanban Board Columns */
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragOver={handleDragOver}
          onDragEnd={handleDragEnd}
        >
          <main className={styles.columnsGrid}>
            {columns.map((column) => (
              <Column
                key={column.id}
                column={column}
                taskIds={order[column.id] || []}
                tasks={tasks}
                allColumns={columns}
                canCreateTask={canCreateTask}
                canDeleteTask={canDeleteTask}
                currentUserId={user?.id || null}
                currentUserRole={currentRole}
                usersMap={usersMap}
                onTaskClick={handleTaskClick}
                onTaskDelete={handleDeleteTask}
                onQuickMove={handleQuickMove}
                onCreateTask={handleCreateTask}
              />
            ))}
          </main>

          <DragOverlay>
            {activeTask && (
              <TaskCard
                task={activeTask}
                onClick={() => {}}
                columns={columns}
                canDrag={true}
                canDelete={false}
                isOverlay={true}
                assigneeName={
                  activeTask.assigneeId
                    ? usersMap[activeTask.assigneeId]
                    : undefined
                }
              />
            )}
          </DragOverlay>
        </DndContext>
      )}

      {/* Task Detail Drawer */}
      <TaskDetailDrawer
        task={detailTask ? tasks[detailTask.id] || detailTask : null}
        columns={columns}
        members={members}
        isOpen={isDetailOpen}
        currentUserRole={currentRole}
        currentUserId={user?.id || null}
        onClose={() => setIsDetailOpen(false)}
        onSave={handleSaveTaskDetail}
        onDelete={handleDeleteTask}
      />

      {/* New Board Modal */}
      <Dialog
        open={isNewBoardOpen}
        title="Create New Board"
        onClose={() => setIsNewBoardOpen(false)}
        footer={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsNewBoardOpen(false)}
              disabled={isCreatingBoard}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleCreateBoard}
              disabled={isCreatingBoard || !newBoardName.trim()}
            >
              {isCreatingBoard ? "Creating…" : "Create"}
            </Button>
          </>
        }
      >
        <form onSubmit={handleCreateBoard}>
          <TextField
            label="Board Name"
            placeholder="e.g. Q4 Sprint, Product Roadmap"
            value={newBoardName}
            onChange={(e) => setNewBoardName(e.target.value)}
            required
            autoFocus
          />
        </form>
      </Dialog>

      {/* Toast notifications */}
      {toastMessage && (
        <Toast
          message={toastMessage}
          onDismiss={() => setToastMessage(null)}
          duration={3500}
        />
      )}
    </div>
  );
}
