import {
    TOOL_CALL_COMPLETED_EVENT_TYPE,
    VERIFICATION_CHECKS_COMPLETED_EVENT_TYPE,
    type RunTimelineEvent,
} from '../../services/bmadService';
import { summarizeToolPayload } from './toolEventPresentation';

/** Human-readable labels for timeline (aligned with FR17). */
const PHASE_DISPLAY_NAMES: Record<string, string> = {
  prd: 'PRD',
  architecture: 'Architecture',
  stories: 'Stories',
  code: 'Code',
};

export function getPhaseDisplayName(phaseId: string | null | undefined): string {
  if (phaseId == null || phaseId === '') return '—';
  return PHASE_DISPLAY_NAMES[phaseId] ?? phaseId;
}

export type TimelineRowVariant =
  | 'failure'
  | 'tool'
  | 'phase-transition'
  | 'phase-governance'
  | 'phase-status'
  | 'default';

const MAX_FAILURE_ONE_LINE = 120;

function truncateOneLine(text: string, max: number): string {
  const t = text.replace(/\s+/g, ' ').trim();
  if (t.length <= max) return t;
  return `${t.slice(0, Math.max(0, max - 1))}…`;
}

const STEP_DISPLAY: Record<string, string> = {
  'generate-phase-proposal': 'generate phase proposal',
  'modify-regenerate-proposal': 'modify / regenerate proposal',
};

function humanizeStep(step: string | undefined): string {
  if (step == null || step === '') return '—';
  return STEP_DISPLAY[step] ?? step.replace(/-/g, ' ');
}

/**
 * Failure/diagnostic rows (FR18): distinct from normal tool / phase-transition / governance rows.
 * Tool rows with `error_summary` use variant **failure** (not `tool`) for consistent error styling.
 */
export function isFailureTimelineEvent(event: RunTimelineEvent): boolean {
  if (event.event_type === 'proposal_generation_failed') return true;
  if (event.event_type === 'resume-failed') return true;
  if (event.event_type === 'phase-status-changed' && event.new_status === 'failed') return true;
  if (
    event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE
    && typeof event.error_summary === 'string'
    && event.error_summary.trim() !== ''
  ) {
    return true;
  }
  return false;
}

const PHASE_GOVERNANCE_TYPES = new Set([
  'phase-approved',
  'phase-awaiting-transition',
  'phase-transition-blocked',
  'verification_gate_blocked',
  'proposal_generated',
  'phase-context-consumed',
  VERIFICATION_CHECKS_COMPLETED_EVENT_TYPE,
  'correction_proposed',
  'correction_applied',
]);

/**
 * Maps API event_type (+ optional reason) to a row presentation variant.
 * Tool rows stay isolated from phase styling (Story 3.2); failures are distinct (Story 3.6).
 */
export function classifyTimelineRowVariant(event: RunTimelineEvent): TimelineRowVariant {
  if (isFailureTimelineEvent(event)) {
    return 'failure';
  }
  if (event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE) {
    return 'tool';
  }
  if (event.event_type === 'phase-transition') {
    return 'phase-transition';
  }
  if (event.event_type === 'phase-status-changed') {
    return 'phase-status';
  }
  if (PHASE_GOVERNANCE_TYPES.has(event.event_type)) {
    return 'phase-governance';
  }
  return 'default';
}

/** One-line summary for collapsed failure rows: phase label + step (when present) + short diagnostic (FR18). */
export function formatFailureEventSummary(event: RunTimelineEvent): string {
  const phaseLabel = getPhaseDisplayName(event.phase);

  if (event.event_type === 'proposal_generation_failed') {
    const stepText = humanizeStep(event.step);
    const hint = truncateOneLine(
      event.error_summary?.trim() || event.reason?.trim() || 'proposal generation failed',
      MAX_FAILURE_ONE_LINE,
    );
    return `${phaseLabel} · ${stepText} · ${hint}`;
  }

  if (event.event_type === 'resume-failed') {
    const hint = truncateOneLine(event.reason?.trim() || 'resume failed', MAX_FAILURE_ONE_LINE);
    return `${phaseLabel} · resume failed · ${hint}`;
  }

  if (event.event_type === 'phase-status-changed' && event.new_status === 'failed') {
    const hint = truncateOneLine(event.reason?.trim() || 'phase status failed', MAX_FAILURE_ONE_LINE);
    return `${phaseLabel} · status → failed · ${hint}`;
  }

  if (event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE && event.error_summary) {
    const name = event.tool_name || 'tool';
    const hint = truncateOneLine(event.error_summary.trim(), MAX_FAILURE_ONE_LINE);
    return `${phaseLabel} · tool ${name} · ${hint}`;
  }

  return truncateOneLine(event.error_summary?.trim() || event.reason?.trim() || 'failure', MAX_FAILURE_ONE_LINE);
}

/**
 * Effective “working phase” for this row: transition uses next_phase; else event.phase;
 * else carry forward previous scope (phase-agnostic rows stay under the last known phase).
 */
export function effectiveScopePhaseForRow(
  event: RunTimelineEvent,
  previousScope: string | null,
): string | null {
  if (event.event_type === 'phase-transition' && event.next_phase) {
    return event.next_phase;
  }
  if (event.phase) {
    return event.phase;
  }
  return previousScope;
}

export function formatPhaseTransitionSummary(event: RunTimelineEvent): string {
  const from = getPhaseDisplayName(event.previous_phase ?? undefined);
  const to = getPhaseDisplayName(event.next_phase ?? undefined);
  const parts = [`Phase transition: ${from} → ${to}`];
  if (event.trigger && event.trigger.trim()) {
    parts.push(`trigger: ${event.trigger}`);
  }
  return parts.join(' · ');
}

export function formatEventDetailForTimeline(event: RunTimelineEvent): string {
  if (isFailureTimelineEvent(event)) {
    return formatFailureEventSummary(event);
  }

  if (event.event_type === TOOL_CALL_COMPLETED_EVENT_TYPE) {
    const name = event.tool_name || 'unknown_tool';
    if (name === 'web_search') {
      const input = typeof event.tool_input === 'object' && event.tool_input !== null
        ? (event.tool_input as Record<string, unknown>)
        : {};
      const output = typeof event.tool_output === 'object' && event.tool_output !== null
        ? (event.tool_output as Record<string, unknown>)
        : {};
      const querySummary = summarizeToolPayload(input.query ?? '');
      const resultSummary = summarizeToolPayload(output.results ?? []);
      return `Tool: web_search | query: ${querySummary} | results: ${resultSummary}`;
    }
    const inSummary = summarizeToolPayload(event.tool_input);
    const outSummary = summarizeToolPayload(event.tool_output);
    return `Tool: ${name} | in: ${inSummary} | out: ${outSummary}`;
  }

  if (event.event_type === 'phase-transition') {
    return formatPhaseTransitionSummary(event);
  }

  if (event.event_type === VERIFICATION_CHECKS_COMPLETED_EVENT_TYPE) {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const s = event.summary;
    const pass = s?.pass_count ?? '—';
    const fail = s?.fail_count ?? '—';
    const overall = s?.overall ?? '—';
    return `${phaseLabel} · verification · pass ${pass} · fail ${fail} · ${overall}`;
  }

  if (event.event_type === 'correction_proposed') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const source = event.source_check_id ?? 'unknown-check';
    const mismatch = event.mismatch_id ? ` · ${event.mismatch_id}` : '';
    const summary = event.compact_summary;
    const note = typeof summary === 'string' && summary.trim() ? ` · ${summary}` : '';
    return `${phaseLabel} · correction proposed · ${source}${mismatch}${note}`;
  }

  if (event.event_type === 'correction_applied') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const source = event.source_check_id ?? 'unknown-check';
    const before = event.before_verification_overall ?? 'unknown';
    const after = event.after_verification_overall ?? event.summary?.overall ?? 'unknown';
    const result = event.result ? ` · result ${event.result}` : '';
    return `${phaseLabel} · correction applied · ${source} · verification ${before} → ${after}${result}`;
  }

  if (event.event_type === 'phase-status-changed') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    return `${phaseLabel}: ${event.old_status || 'unknown'} → ${event.new_status || 'unknown'} (${event.reason || 'n/a'})`;
  }

  if (event.event_type === 'phase-approved' || event.event_type === 'phase-awaiting-transition') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const detail = event.reason ? ` · ${event.reason}` : '';
    return `${event.event_type.replace(/-/g, ' ')} · ${phaseLabel}${detail}`;
  }

  if (event.event_type === 'phase-transition-blocked') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const unresolvedCount = event.blocker?.unresolved_critical_count;
    if (typeof unresolvedCount === 'number') {
      return `Blocked · ${phaseLabel} · unresolved critical checks ${unresolvedCount}`;
    }
    return `Blocked · ${phaseLabel}${event.reason ? ` · ${event.reason}` : ''}`;
  }

  if (event.event_type === 'verification_gate_blocked') {
    const phaseLabel = getPhaseDisplayName(event.phase);
    const unresolvedCount = event.blocker?.unresolved_critical_count;
    const nextAction = event.blocker?.next_action;
    if (typeof unresolvedCount === 'number') {
      return `Verification gate blocked · ${phaseLabel} · unresolved critical checks ${unresolvedCount}${nextAction ? ` · ${nextAction}` : ''}`;
    }
    return `Verification gate blocked · ${phaseLabel}`;
  }

  if (event.previous_phase || event.next_phase) {
    return `${getPhaseDisplayName(event.previous_phase ?? undefined)} → ${getPhaseDisplayName(event.next_phase ?? undefined)}`;
  }

  if (event.context_source || event.context_version !== undefined) {
    return `source: ${event.context_source || 'n/a'}, version: ${event.context_version ?? 'n/a'}`;
  }

  if (event.error_summary) {
    return event.error_summary;
  }

  return event.reason || 'No additional detail';
}
