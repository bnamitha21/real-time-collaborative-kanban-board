import React, { useState, useRef, useEffect } from "react";
import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import styles from "./Column.module.css";
import { TaskCard } from "./TaskCard";
import { Button } from "../ui";
import { PlusIcon } from "../icons";
import type { TaskDto, ColumnDto } from "../../store/board";

export interface ColumnProps {
  column: ColumnDto;
  taskIds: string[];
  tasks: Record<string, TaskDto>;
  allColumns: ColumnDto[];
  canCreateTask: boolean;
  canDeleteTask: boolean;
  currentUserId: string | null;
  currentUserRole: string | null;
  usersMap?: Record<string, string>;
  onTaskClick: (task: TaskDto) => void;
  onTaskDelete?: (task: TaskDto) => void;
  onQuickMove?: (task: TaskDto, toColumnId: string) => void;
  onCreateTask?: (columnId: string, title: string) => Promise<void>;
}

export function Column({
  column,
  taskIds,
  tasks,
  allColumns,
  canCreateTask,
  canDeleteTask,
  currentUserId,
  currentUserRole,
  usersMap = {},
  onTaskClick,
  onTaskDelete,
  onQuickMove,
  onCreateTask,
}: ColumnProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const { setNodeRef } = useDroppable({
    id: column.id,
    data: {
      type: "Column",
      columnId: column.id,
    },
  });

  useEffect(() => {
    if (isAdding) {
      inputRef.current?.focus();
    }
  }, [isAdding]);

  const handleCreateSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!newTitle.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      if (onCreateTask) {
        await onCreateTask(column.id, newTitle.trim());
      }
      setNewTitle("");
      setIsAdding(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleCreateSubmit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsAdding(false);
      setNewTitle("");
    }
  };

  const headerColorClass =
    column.key === "todo"
      ? styles.headerTodo
      : column.key === "in_progress"
      ? styles.headerProgress
      : styles.headerDone;

  return (
    <section className={styles.column} aria-label={`${column.name} column`}>
      <header className={`${styles.header} ${headerColorClass}`}>
        <div className={styles.titleArea}>
          <h3 className={styles.title}>{column.name}</h3>
          <span className={styles.count} aria-label={`${taskIds.length} tasks`}>
            {taskIds.length}
          </span>
        </div>
      </header>

      <div ref={setNodeRef} className={styles.cardList}>
        <SortableContext items={taskIds} strategy={verticalListSortingStrategy}>
          {taskIds.map((taskId) => {
            const task = tasks[taskId];
            if (!task) return null;

            // Members can only drag their own assigned tasks
            const isAssignee = task.assigneeId === currentUserId;
            const canDrag =
              currentUserRole === "org_admin" ||
              currentUserRole === "tenant_admin" ||
              (currentUserRole === "member" && isAssignee);

            return (
              <TaskCard
                key={task.id}
                task={task}
                onClick={onTaskClick}
                onDelete={onTaskDelete}
                onQuickMove={onQuickMove}
                columns={allColumns}
                canDrag={canDrag}
                canDelete={canDeleteTask}
                assigneeName={
                  task.assigneeId ? usersMap[task.assigneeId] : undefined
                }
              />
            );
          })}
        </SortableContext>

        {taskIds.length === 0 && (
          <div className={styles.emptyState}>No tasks in this column</div>
        )}
      </div>

      {column.key === "todo" && canCreateTask && (
        <footer className={styles.footer}>
          {isAdding ? (
            <form onSubmit={handleCreateSubmit} className={styles.inlineForm}>
              <input
                ref={inputRef}
                type="text"
                className={styles.inlineInput}
                placeholder="What needs to be done?"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isSubmitting}
              />
              <div className={styles.inlineFormActions}>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  disabled={isSubmitting || !newTitle.trim()}
                >
                  {isSubmitting ? "Adding…" : "Add task"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsAdding(false);
                    setNewTitle("");
                  }}
                  disabled={isSubmitting}
                >
                  Cancel
                </Button>
              </div>
            </form>
          ) : (
            <button
              type="button"
              className={styles.addTaskButton}
              onClick={() => setIsAdding(true)}
            >
              <PlusIcon size={14} />
              <span>Add task</span>
            </button>
          )}
        </footer>
      )}
    </section>
  );
}

