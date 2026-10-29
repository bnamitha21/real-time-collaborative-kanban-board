import React, { useState, useRef, useEffect } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import styles from "./TaskCard.module.css";
import { Avatar } from "../ui";
import { DotsIcon, TrashIcon, ArrowRightIcon } from "../icons";
import type { TaskDto, ColumnDto } from "../../store/board";

export interface TaskCardProps {
  task: TaskDto;
  onClick: (task: TaskDto) => void;
  onDelete?: (task: TaskDto) => void;
  onQuickMove?: (task: TaskDto, toColumnId: string) => void;
  columns?: ColumnDto[];
  canDrag: boolean;
  canDelete: boolean;
  isOverlay?: boolean;
  assigneeName?: string;
  dragDisabledTooltip?: string;
}

export function TaskCard({
  task,
  onClick,
  onDelete,
  onQuickMove,
  columns = [],
  canDrag,
  canDelete,
  isOverlay = false,
  assigneeName,
  dragDisabledTooltip = "Only the assignee can move this task",
}: TaskCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: task.id,
    disabled: !canDrag || isOverlay,
  });

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition,
  };

  useEffect(() => {
    if (!menuOpen) return;
    const handleOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [menuOpen]);

  const priorityClass =
    task.priority === "high"
      ? styles.priorityHigh
      : task.priority === "medium"
      ? styles.priorityMedium
      : styles.priorityLow;

  const cardClasses = [
    styles.card,
    isDragging ? styles.dragging : "",
    isOverlay ? styles.overlayCard : "",
  ]
    .filter(Boolean)
    .join(" ");

  const otherColumns = columns.filter((c) => c.id !== task.columnId);

  const handleCardClick = () => {
    if (menuOpen) return;
    onClick(task);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      if (document.activeElement === e.currentTarget) {
        e.preventDefault();
        onClick(task);
      }
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cardClasses}
      onClick={handleCardClick}
      onKeyDown={handleKeyDown}
      aria-label={`${task.title}, priority ${task.priority}, version ${task.version}`}
      title={!canDrag ? dragDisabledTooltip : undefined}
      {...(!isOverlay ? attributes : {})}
      {...(!isOverlay && canDrag ? listeners : {})}
    >
      {/* Priority Left Accent Bar */}
      <div className={`${styles.priorityIndicator} ${priorityClass}`} />

      <div className={styles.cardHeader}>
        <h4 className={styles.title}>{task.title}</h4>

        {!isOverlay && (
          <div
            className={styles.contextMenuWrapper}
            ref={menuRef}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className={styles.menuTrigger}
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="Task options"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
            >
              <DotsIcon size={14} />
            </button>

            {menuOpen && (
              <div className={styles.contextMenu} role="menu">
                <button
                  type="button"
                  className={styles.menuItem}
                  onClick={() => {
                    setMenuOpen(false);
                    onClick(task);
                  }}
                  role="menuitem"
                >
                  Open details
                </button>

                {onQuickMove &&
                  otherColumns.map((col) => (
                    <button
                      key={col.id}
                      type="button"
                      className={styles.menuItem}
                      onClick={() => {
                        setMenuOpen(false);
                        onQuickMove(task, col.id);
                      }}
                      role="menuitem"
                    >
                      <ArrowRightIcon size={12} />
                      <span>Move to {col.name}</span>
                    </button>
                  ))}

                {canDelete && onDelete && (
                  <button
                    type="button"
                    className={`${styles.menuItem} ${styles.menuItemDanger}`}
                    onClick={() => {
                      setMenuOpen(false);
                      onDelete(task);
                    }}
                    role="menuitem"
                  >
                    <TrashIcon size={12} />
                    <span>Delete</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className={styles.cardFooter}>
        <div className={styles.metaLeft}>
          <span className={styles.versionBadge}>v{task.version}</span>
          {task.pending && <span className={styles.pendingBadge}>Pending</span>}
        </div>

        <div className={styles.metaRight}>
          {task.assigneeId && assigneeName && (
            <Avatar
              name={assigneeName}
              id={task.assigneeId}
              size="sm"
            />
          )}
        </div>
      </div>
    </div>
  );
}
