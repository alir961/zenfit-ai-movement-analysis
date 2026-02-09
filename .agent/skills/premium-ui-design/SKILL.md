---
description: Premium UI/UX Design System - Professional patterns and micro-interactions
---

# Premium UI/UX Design Skill

This skill provides comprehensive guidelines for creating professional, luxury-grade user interfaces with sophisticated micro-interactions, animations, and layout systems.

## Core Principles

### 1. Micro-Interactions (200-500ms)

**Timing Guidelines**:
- **Fast feedback**: 150-200ms for instant responses (button press, toggle)
- **Standard transitions**: 300ms for most UI changes (modal open, card flip)
- **Slow reveals**: 400-500ms for dramatic effects (hero entrance, page transition)
- **Never exceed**: 1000ms (feels like a delay)

**Four Components**:
1. **Trigger**: User action or system event
2. **Rules**: Logic defining what happens
3. **Feedback**: Visual/audible response
4. **Loops/Modes**: Behavior over time

**Examples**:
```css
/* Button Press - 200ms */
.btn:active {
  transform: scale(0.95);
  transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Card Hover - 300ms */
.card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-xl);
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

/* Modal Open - 400ms */
.modal {
  animation: modalSlideIn 400ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
}
```

### 2. Animation Patterns

**Liquid Motion Design**:
- Seamless, fluid transitions
- Organic, natural movement
- Reduces friction, increases engagement

**Easing Functions**:
```css
/* Standard ease-out (most common) */
cubic-bezier(0.4, 0, 0.2, 1)

/* Bounce effect (playful) */
cubic-bezier(0.68, -0.55, 0.265, 1.55)

/* Sharp entrance (attention-grabbing) */
cubic-bezier(0.4, 0, 1, 1)

/* Smooth deceleration (elegant) */
cubic-bezier(0, 0, 0.2, 1)
```

**Layered Animations**:
```css
/* Stagger children for depth */
.item:nth-child(1) { animation-delay: 0ms; }
.item:nth-child(2) { animation-delay: 100ms; }
.item:nth-child(3) { animation-delay: 200ms; }
```

### 3. Golden Ratio Layouts (1:1.618)

**Screen Division**:
- Main content: 61.8% width
- Sidebar: 38.2% width

**Element Proportions**:
- Button: 100px × 62px
- Card: 400px × 247px
- Hero image: 1618px × 1000px

**Typography Scale**:
```
Base: 16px
H6: 16px × 1.618 = 26px
H5: 26px × 1.618 = 42px
H4: 42px × 1.618 = 68px
```

### 4. Spacing System (4-Point Grid)

**Base Unit**: 4px

**Scale**:
```
--space-1: 4px
--space-2: 8px
--space-3: 12px
--space-4: 16px
--space-6: 24px
--space-8: 32px
--space-12: 48px
--space-16: 64px
--space-24: 96px
```

**Usage**:
- Padding: Multiples of 4
- Margins: Multiples of 4
- Line height: Multiples of 4
- Element sizes: Multiples of 4

## Component Patterns

### Premium Button

```css
.btn-premium {
  /* Base */
  padding: 12px 24px; /* 3 × 4, 6 × 4 */
  border-radius: 12px;
  font-weight: 900;
  
  /* Gradient */
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-hover));
  
  /* Shadow */
  box-shadow: 0 4px 12px rgba(121, 31, 224, 0.25);
  
  /* Transition */
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-premium:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: 0 8px 24px rgba(121, 31, 224, 0.35);
}

.btn-premium:active {
  transform: translateY(0) scale(0.98);
  transition-duration: 150ms;
}

/* Gold shimmer on hover */
.btn-premium::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(238, 190, 17, 0.3), transparent);
  transition: left 600ms;
}

.btn-premium:hover::before {
  left: 100%;
}
```

### Luxury Card

```css
.card-luxury {
  /* Golden ratio dimensions */
  aspect-ratio: 1.618 / 1;
  
  /* Spacing */
  padding: 24px; /* 6 × 4 */
  border-radius: 24px; /* 6 × 4 */
  
  /* Surface */
  background: white;
  border: 1px solid var(--color-deep-mocha-100);
  
  /* Transition */
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.card-luxury:hover {
  transform: translateY(-8px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  border-color: var(--color-accent);
}

/* Gold accent on hover */
.card-luxury::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 0;
  background: var(--color-accent);
  transition: height 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.card-luxury:hover::after {
  height: 100%;
}
```

### Smooth Modal

```css
/* Backdrop */
.modal-backdrop {
  background: rgba(24, 6, 45, 0.8);
  backdrop-filter: blur(12px);
  animation: fadeIn 300ms ease-out;
}

/* Modal */
.modal-content {
  border-radius: 32px;
  padding: 32px;
  background: white;
  animation: modalSlideIn 400ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

@keyframes modalSlideIn {
  from {
    opacity: 0;
    transform: translateY(-20px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
```

### Interactive Input

```css
.input-premium {
  /* Spacing */
  padding: 12px 16px;
  border-radius: 12px;
  
  /* Border */
  border: 2px solid var(--color-deep-mocha-200);
  background: var(--color-surface-elevated);
  
  /* Transition */
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.input-premium:focus {
  border-color: var(--color-primary);
  background: var(--color-surface);
  box-shadow: 0 0 0 4px var(--color-primary-subtle);
  transform: scale(1.01);
}

/* Floating label */
.input-group:focus-within .label {
  transform: translateY(-24px) scale(0.85);
  color: var(--color-primary);
}
```

## Accessibility

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Focus States

```css
.interactive:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--color-surface),
              0 0 0 5px var(--color-primary);
}
```

## Performance

### GPU Acceleration

```css
/* Use transform and opacity for animations */
.animated {
  will-change: transform, opacity;
  transform: translateZ(0); /* Force GPU */
}

/* Avoid animating: */
/* - width/height (causes reflow) */
/* - top/left (causes reflow) */
/* - margin/padding (causes reflow) */
```

### Optimization

```css
/* Limit will-change to active elements only */
.card:hover {
  will-change: transform;
}

.card:not(:hover) {
  will-change: auto;
}
```

## Implementation Checklist

- [ ] Define all timing variables (fast, base, slow)
- [ ] Create easing function library
- [ ] Establish spacing scale (4-point grid)
- [ ] Apply golden ratio to layouts
- [ ] Add micro-interactions to all interactive elements
- [ ] Implement staggered animations for lists
- [ ] Add shimmer/glow effects to premium elements
- [ ] Test with `prefers-reduced-motion`
- [ ] Verify performance (60fps)
- [ ] Document all patterns

## Examples in Context

### Article Card Enhancement

```css
.article-card {
  transition: all 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.article-card:hover {
  transform: translateY(-4px);
}

.article-card:hover .article-image {
  transform: scale(1.05);
  transition: transform 500ms cubic-bezier(0.4, 0, 0.2, 1);
}

.article-card:hover .article-title {
  color: var(--color-primary);
  transition: color 200ms;
}

.article-card .like-button:active {
  animation: heartBeat 300ms cubic-bezier(0.68, -0.55, 0.265, 1.55);
}
```

### Navigation Enhancement

```css
.nav-link {
  position: relative;
  transition: color 200ms;
}

.nav-link::after {
  content: '';
  position: absolute;
  bottom: -4px;
  left: 0;
  width: 0;
  height: 2px;
  background: var(--color-accent);
  transition: width 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.nav-link:hover::after {
  width: 100%;
}
```

---

**Remember**: Every animation should have a purpose. Delight users, don't distract them.
