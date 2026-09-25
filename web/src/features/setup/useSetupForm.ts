import { useReducer } from 'react';

import type { Options } from '@/api/types';

import { initialSetup, normalizeSeat, resizeSeats, type SeatConfig, type SetupState } from './model';

type ScalarField = Exclude<keyof SetupState, 'seats' | 'nPlayers'>;

export type SetupAction =
  | { type: 'setPlayers'; n: number; options: Options | null }
  | { type: 'updateSeat'; index: number; patch: Partial<SeatConfig>; options: Options | null }
  | { type: 'applyAll'; seat: SeatConfig; options: Options | null }
  | { [K in ScalarField]: { type: 'set'; field: K; value: SetupState[K] } }[ScalarField];

export function setupReducer(state: SetupState, action: SetupAction): SetupState {
  switch (action.type) {
    case 'setPlayers':
      return { ...state, nPlayers: action.n, seats: resizeSeats(state.seats, action.n, action.options) };
    case 'updateSeat': {
      const seats = state.seats.map((s, i) =>
        i === action.index ? normalizeSeat({ ...s, ...action.patch }, action.options) : s,
      );
      return { ...state, seats };
    }
    case 'applyAll':
      return { ...state, seats: state.seats.map(() => normalizeSeat(action.seat, action.options)) };
    case 'set':
      return { ...state, [action.field]: action.value };
  }
}

export function useSetupForm(options: Options) {
  return useReducer(setupReducer, options, initialSetup);
}
