import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { Check, Loader2, MapPin, X } from 'lucide-react';
import { searchGeocode, SpotterApiError } from '../../../shared/api/client';
import type { GeocodeResponse, GeoLocation } from '../../../shared/types/plan';

export interface LocationAutocompleteProps {
  label: string;
  placeholder: string;
  value: GeoLocation | null;
  onChange: (location: GeoLocation | null) => void;
  error?: string;
  disabled?: boolean;
  /** Optional custom search function (used for testing or custom providers). */
  searchFn?: (query: string, signal?: AbortSignal) => Promise<GeocodeResponse>;
  /** Marker accent dot distinguishing origin vs destination. */
  markerTone?: 'origin' | 'destination';
  onDataModeDetected?: (mode: 'live' | 'fixture') => void;
}

const DEBOUNCE_MS = 220;
const MIN_QUERY_LENGTH = 2;

export function LocationAutocomplete({
  label,
  placeholder,
  value,
  onChange,
  error,
  disabled = false,
  searchFn = searchGeocode,
  markerTone = 'origin',
  onDataModeDetected,
}: LocationAutocompleteProps) {
  const inputId = useId();
  const listboxId = useId();
  const errorId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [inputText, setInputText] = useState<string>(value?.label ?? '');
  const [results, setResults] = useState<GeoLocation[]>([]);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const [hasSearched, setHasSearched] = useState<boolean>(false);

  // Sync displayed text when parent updates value (e.g., Swap origin/destination)
  useEffect(() => {
    setInputText(value?.label ?? '');
  }, [value]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      if (
        containerRef.current &&
        event.target instanceof Node &&
        !containerRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Debounced, abortable geocoding lookup when user types an unselected query
  useEffect(() => {
    const trimmed = inputText.trim();

    // Do not search if input matches the already-confirmed selected location
    if (value && trimmed === value.label) {
      setIsLoading(false);
      setFetchError(null);
      return;
    }

    if (trimmed.length < MIN_QUERY_LENGTH) {
      setResults([]);
      setIsLoading(false);
      setFetchError(null);
      setHasSearched(false);
      setActiveIndex(-1);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setFetchError(null);
      try {
        const response = await searchFn(trimmed, controller.signal);
        if (controller.signal.aborted) return;
        if (response.data_mode && onDataModeDetected) {
          onDataModeDetected(response.data_mode);
        }
        setResults(response.results);
        setHasSearched(true);
        setIsOpen(true);
        setActiveIndex(response.results.length > 0 ? 0 : -1);
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message =
          err instanceof SpotterApiError
            ? err.detail.message
            : 'Location search is temporarily unavailable. Try again.';
        setFetchError(message);
        setResults([]);
        setHasSearched(true);
        setIsOpen(true);
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [inputText, value, searchFn, onDataModeDetected]);

  function selectOption(location: GeoLocation) {
    setInputText(location.label);
    onChange(location);
    setIsOpen(false);
    setResults([]);
    setFetchError(null);
    setActiveIndex(-1);
  }

  function handleClear() {
    setInputText('');
    onChange(null);
    setResults([]);
    setFetchError(null);
    setIsOpen(false);
    setHasSearched(false);
    setActiveIndex(-1);
    inputRef.current?.focus();
  }

  function handleInputChange(nextText: string) {
    setInputText(nextText);
    if (value && nextText !== value.label) {
      // Editing text invalidates previously confirmed coordinates until user explicitly chooses again
      onChange(null);
    }
    if (nextText.trim().length >= MIN_QUERY_LENGTH) {
      setIsOpen(true);
    } else {
      setIsOpen(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!isOpen && (event.key === 'ArrowDown' || event.key === 'ArrowUp')) {
      if (results.length > 0) {
        event.preventDefault();
        setIsOpen(true);
        setActiveIndex(0);
      }
      return;
    }

    if (!isOpen) return;

    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        setActiveIndex((prev) => (results.length === 0 ? -1 : (prev + 1) % results.length));
        break;
      case 'ArrowUp':
        event.preventDefault();
        setActiveIndex((prev) =>
          results.length === 0 ? -1 : prev <= 0 ? results.length - 1 : prev - 1,
        );
        break;
      case 'Enter':
        if (activeIndex >= 0 && results[activeIndex]) {
          event.preventDefault();
          selectOption(results[activeIndex]);
        }
        break;
      case 'Escape':
        event.preventDefault();
        setIsOpen(false);
        break;
    }
  }

  const activeOptionId =
    isOpen && activeIndex >= 0 && results[activeIndex]
      ? `${listboxId}-opt-${activeIndex}`
      : undefined;

  const showAmbiguousHint =
    isOpen && results.length > 1 && !value && !isLoading && !fetchError;

  const displayedError = error ?? fetchError ?? undefined;

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-center justify-between mb-1.5">
        <label
          htmlFor={inputId}
          className="text-[13px] font-medium text-[var(--color-ink)] flex items-center gap-1.5"
        >
          <span
            aria-hidden="true"
            className="h-2 w-2 rounded-full shrink-0"
            style={{
              backgroundColor:
                markerTone === 'origin'
                  ? 'var(--color-brand-deep)'
                  : 'var(--color-brand-action)',
            }}
          />
          {label}
        </label>
        {value ? (
          <span className="inline-flex items-center gap-1 text-[11.5px] text-[var(--color-brand-action)] font-medium">
            <Check className="h-3 w-3" aria-hidden="true" />
            Verified
          </span>
        ) : null}
      </div>

      <div className="relative">
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          aria-invalid={Boolean(displayedError)}
          aria-describedby={displayedError ? errorId : undefined}
          autoComplete="off"
          disabled={disabled}
          value={inputText}
          placeholder={placeholder}
          onChange={(e) => handleInputChange(e.target.value)}
          onFocus={() => {
            if (!value && results.length > 0) {
              setIsOpen(true);
            }
          }}
          onKeyDown={handleKeyDown}
          className={[
            'w-full h-11 pl-3.5 pr-9 rounded-[var(--radius-control)] text-[14px] text-[var(--color-ink)]',
            'bg-[var(--color-surface)] border transition-[border-color,background-color] duration-[var(--duration-feedback)] ease-[var(--ease-standard)]',
            'placeholder:text-[var(--color-ink-secondary)]/70',
            'disabled:bg-[var(--color-surface-muted)] disabled:cursor-not-allowed',
            displayedError
              ? 'border-[var(--severity-severe)]'
              : value
                ? 'border-[var(--color-brand-action)]/60'
                : 'border-[var(--color-border-strong)] hover:border-[var(--color-brand-action)]/60',
          ].join(' ')}
        />

        <div className="absolute right-2.5 top-1/2 -translate-y-1/2 flex items-center">
          {isLoading ? (
            <Loader2
              className="h-4 w-4 text-[var(--color-ink-secondary)] animate-spin"
              aria-hidden="true"
            />
          ) : inputText.length > 0 && !disabled ? (
            <button
              type="button"
              onClick={handleClear}
              aria-label={`Clear ${label}`}
              className="p-1 rounded-full text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)] hover:bg-[var(--color-surface-muted)] cursor-pointer"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </div>

      {/* Screen-reader announcement for search results */}
      <div className="sr-only" role="status" aria-live="polite">
        {isLoading
          ? `Searching places for ${label}`
          : hasSearched && isOpen
            ? results.length > 0
              ? `${results.length} matching places available for ${label}. Use arrow keys to choose.`
              : `No matching places found for ${label}.`
            : ''}
      </div>

      {isOpen ? (
        <div
          id={listboxId}
          role="listbox"
          aria-label={`${label} suggestions`}
          className="absolute left-0 right-0 mt-1.5 z-[var(--z-popover)] rounded-[var(--radius-card)] border border-[var(--color-border-strong)] bg-[var(--color-surface)] shadow-[var(--shadow-overlay)] overflow-hidden"
        >
          {showAmbiguousHint ? (
            <div className="px-3 py-2 bg-[var(--color-surface-muted)] border-b border-[var(--color-border)] text-[11.5px] font-medium text-[var(--color-ink-secondary)]">
              Choose the correct location — multiple places match
            </div>
          ) : null}

          {results.length > 0 ? (
            <ul className="m-0 p-1 list-none max-h-60 overflow-y-auto spotter-scroll">
              {results.map((item, idx) => {
                const isActive = idx === activeIndex;
                return (
                  <li
                    key={item.place_id ?? `${item.latitude},${item.longitude},${idx}`}
                    id={`${listboxId}-opt-${idx}`}
                    role="option"
                    aria-selected={isActive}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectOption(item);
                    }}
                    className={[
                      'flex items-start gap-2.5 px-2.5 py-2 rounded-[9px] cursor-pointer text-left',
                      isActive
                        ? 'bg-[var(--color-brand-tint)] text-[var(--color-brand-deep)]'
                        : 'text-[var(--color-ink)] hover:bg-[var(--color-surface-hover)]',
                    ].join(' ')}
                  >
                    <MapPin
                      className="h-4 w-4 shrink-0 mt-0.5 text-[var(--color-brand-action)]"
                      aria-hidden="true"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] font-medium truncate">{item.label}</div>
                      {item.subtitle ? (
                        <div className="text-[12px] text-[var(--color-ink-secondary)] truncate">
                          {item.subtitle}
                        </div>
                      ) : (
                        <div className="text-[11.5px] text-[var(--color-ink-secondary)] tabular-nums">
                          {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : hasSearched && !isLoading && !fetchError ? (
            <div className="px-3.5 py-3 text-[13px] text-[var(--color-ink-secondary)]">
              No recognized places found. Try including a city and state.
            </div>
          ) : null}
        </div>
      ) : null}

      {displayedError ? (
        <p
          id={errorId}
          role="alert"
          className="mt-1.5 text-[12.5px] text-[var(--severity-severe)] m-0 leading-snug"
        >
          {displayedError}
        </p>
      ) : null}
    </div>
  );
}
