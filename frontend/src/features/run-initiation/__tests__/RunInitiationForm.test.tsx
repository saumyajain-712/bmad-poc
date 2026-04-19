import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RunInitiationForm from '../RunInitiationForm';

vi.mock('../../../services/bmadService', () => ({
  createRun: vi.fn(),
  submitRunClarifications: vi.fn(),
  fetchRun: vi.fn(),
  applyPhaseCorrection: vi.fn(),
  resetRunEnvironment: vi.fn(),
}));

vi.mock('../../run-observability/RunTimeline', () => ({
  default: () => <div data-testid="run-timeline" />,
}));

import { applyPhaseCorrection, createRun, fetchRun, resetRunEnvironment } from '../../../services/bmadService';

const buildRun = (overrides: Record<string, unknown> = {}) => ({
  id: 99,
  status: 'awaiting-approval',
  original_input: 'Create todo API',
  resolved_input_context: 'resolved context',
  context_version: 1,
  context_events: [],
  phase_statuses: { code: 'awaiting-approval' },
  phase_status_badges: { 'awaiting-approval': 'awaiting-approval' },
  current_phase_proposal: {
    phase: 'code',
    revision: 1,
    verification: { overall: 'failed', checks: [] },
    correction_proposal: {
      mismatch_id: 'code-todo-api-ui',
      source_check_id: 'code-todo-api-ui',
      recommended_change_target: 'frontend todo-create request payload',
      patch_guidance: 'Include completed field',
    },
  },
  verification_review: {
    phase: 'code',
    proposal_revision: 1,
    verification: {
      overall: 'failed',
      pass_count: 7,
      fail_count: 1,
      failed_checks: [{ id: 'code-todo-api-ui', severity: 'critical', message: 'mismatch' }],
    },
    correction: {
      state: 'proposed',
      mismatch_id: 'code-todo-api-ui',
      mismatch_category: 'code',
    },
    blocker: {
      error_code: 'unresolved_verification_blocker',
      message: 'Progression blocked until unresolved critical verification mismatches are fixed.',
      unresolved_critical_count: 1,
      next_action: 'Apply or implement corrective changes and re-run verification.',
    },
    status: 'blocked',
    required_next_action: 'Apply or implement corrective changes and re-run verification.',
    deterministic_signature: 'code|rev-1|ver-failed|corr-proposed|blocked-True',
  },
  final_output_review: {
    phase: 'code',
    proposal_revision: 1,
    artifact_summary: {
      title: 'CODE Proposal',
      summary: 'Generated backend and frontend todo artifacts.',
      backend_files: ['backend/main.py'],
      frontend_files: ['frontend/src/features/todos/TodoApp.tsx'],
      total_files: 2,
    },
    review_access: {
      local_only: true,
      backend_command: 'cd backend && uvicorn main:app --reload',
      frontend_command: 'cd frontend && npm run dev',
      frontend_url: 'http://localhost:3000',
      api_base_url: 'http://localhost:8000/api/v1',
    },
    verification_overview: {
      overall: 'failed',
      blocked: true,
      blocker: {
        message: 'Progression blocked until unresolved critical verification mismatches are fixed.',
      },
    },
    deterministic_signature: 'code|rev-1|gen-run-99|files-2|blocked-True',
  },
  ...overrides,
});

describe('RunInitiationForm correction apply controls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('shows apply correction button only when correction proposal exists', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(await screen.findByRole('button', { name: /Apply correction/i })).toBeInTheDocument();

    vi.mocked(createRun).mockResolvedValueOnce({
      run: buildRun({
        current_phase_proposal: {
          phase: 'code',
          revision: 1,
          verification: { overall: 'passed', checks: [] },
        },
      }),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api again' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Apply correction/i })).not.toBeInTheDocument();
    });
  });

  it('disables apply button while request is in progress', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    let resolveApply: ((value: unknown) => void) | null = null;
    const pendingApply = new Promise((resolve) => {
      resolveApply = resolve;
    });
    vi.mocked(applyPhaseCorrection).mockReturnValue(pendingApply as Promise<never>);
    vi.mocked(fetchRun).mockResolvedValue(buildRun());

    render(<RunInitiationForm />);

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    const applyButton = await screen.findByRole('button', { name: /Apply correction/i });
    fireEvent.click(applyButton);
    expect(await screen.findByRole('button', { name: /Applying correction/i })).toBeDisabled();

    resolveApply?.({ status: 'correction-applied' });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Apply correction/i })).toBeEnabled();
    });
  });

  it('renders verification review blocker summary and required action', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);
    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(await screen.findByText(/Verification review/i)).toBeInTheDocument();
    expect(screen.getByText(/1 failed \/ 7 passed/i)).toBeInTheDocument();
    expect(screen.getByText(/Correction outcome:/i).parentElement).toHaveTextContent('proposed');
    expect(screen.getAllByText(/Blocker:/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Required next action:/i).parentElement).toHaveTextContent(
      'Apply or implement corrective changes and re-run verification.'
    );
  });

  it('renders final output review panel with local access hints and blocker visibility', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);
    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(await screen.findByText(/Final output review/i)).toBeInTheDocument();
    expect(screen.getByText(/Generated files:/i).parentElement).toHaveTextContent('2');
    expect(screen.getByText(/Run locally:/i).parentElement).toHaveTextContent(
      'cd backend && uvicorn main:app --reload'
    );
    expect(screen.getByText(/Open:/i).parentElement).toHaveTextContent('http://localhost:3000');
    expect(screen.getByText(/Verification blocker:/i)).toBeInTheDocument();
  });
});

describe('RunInitiationForm reset environment (FR29)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  it('calls resetRunEnvironment after confirm and clears run panels', async () => {
    vi.mocked(resetRunEnvironment).mockResolvedValue({
      status: 'ok',
      runs_deleted: 2,
      runs_remaining: 0,
    });
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun(),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);

    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    await screen.findByTestId('run-timeline');

    fireEvent.click(screen.getByRole('button', { name: /Reset environment/i }));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(resetRunEnvironment).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(screen.queryByTestId('run-timeline')).not.toBeInTheDocument();
    });
  });
});

describe('RunInitiationForm run complete (FR28)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows Run complete banner when run_complete is true and verification is not blocked', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun({
        status: 'phase-sequence-complete',
        run_complete: true,
        phase_statuses: {
          prd: 'approved',
          architecture: 'approved',
          stories: 'approved',
          code: 'in-progress',
        },
        verification_review: {
          phase: 'code',
          proposal_revision: 1,
          verification: {
            overall: 'passed',
            pass_count: 8,
            fail_count: 0,
            failed_checks: [],
          },
          correction: { state: 'none', mismatch_id: null },
          status: 'ready',
          required_next_action: 'Ready for approval and phase progression.',
          deterministic_signature: 'code|rev-1|ver-passed|corr-none|blocked-False',
        },
        final_output_review: {
          phase: 'code',
          proposal_revision: 1,
          artifact_summary: {
            title: 'CODE Proposal',
            summary: 'Generated backend and frontend todo artifacts.',
            backend_files: ['backend/main.py'],
            frontend_files: ['frontend/src/features/todos/TodoApp.tsx'],
            total_files: 2,
          },
          review_access: {
            local_only: true,
            backend_command: 'cd backend && uvicorn main:app --reload',
            frontend_command: 'cd frontend && npm run dev',
            frontend_url: 'http://localhost:3000',
            api_base_url: 'http://localhost:8000/api/v1',
          },
          verification_overview: {
            overall: 'passed',
            blocked: false,
            blocker: null,
          },
          deterministic_signature: 'code|rev-1|gen-run-99|files-2|blocked-False',
        },
      }),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);
    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    expect(await screen.findByRole('status', { name: 'Run complete' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Run complete' })).toHaveTextContent(/Run complete/i);
  });

  it('does not show Run complete banner when final output review is blocked even if run_complete is true', async () => {
    vi.mocked(createRun).mockResolvedValue({
      run: buildRun({
        status: 'phase-sequence-complete',
        run_complete: true,
      }),
      validation: { is_complete: true, missing_items: [], clarification_questions: [] },
    });

    render(<RunInitiationForm />);
    fireEvent.change(screen.getByPlaceholderText(/Enter free-text API specification/i), {
      target: { value: 'Create todo api' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Initiate BMAD Run/i }));

    await screen.findByText(/Final output review/i);
    expect(screen.queryByRole('status', { name: 'Run complete' })).not.toBeInTheDocument();
  });
});
