# Authentication Pages Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the login and registration pages into a cohesive, responsive YanJie authentication experience without changing authentication behavior.

**Architecture:** A reusable `AuthShell` owns the desktop/mobile layout and brand-side visual. `LoginView` and `RegisterView` retain their store calls and route semantics while supplying form-specific content and local field presentation state.

**Tech Stack:** Vue 3, TypeScript, Tailwind CSS, Vue Router, Pinia.

## Global Constraints

- Keep `/login`, `/register`, existing API payloads and route redirects unchanged.
- Do not add unimplemented features such as social sign-in, password recovery or email verification.
- Reuse the existing dark palette and respect `prefers-reduced-motion`.
- Use accessible labels, native validation and `aria-live` error feedback.

---

### Task 1: Build the Shared Authentication Shell

**Files:**
- Create: `frontend/src/components/auth/AuthShell.vue`
- Modify: `frontend/src/views/LoginView.vue`
- Test: `frontend` production build

**Interfaces:**
- Consumes: named `title`, `subtitle`, `form`, and `footer` slots.
- Produces: a responsive two-column authentication layout shared by both routes.

- [x] **Step 1: Write the failing component contract check**

Create the shell import and named slots in `LoginView.vue`; run the production build before the component exists.

Run: `cmd.exe /d /c npm run build`

Expected: FAIL because `@/components/auth/AuthShell.vue` cannot be resolved.

- [x] **Step 2: Implement the shell**

Create `AuthShell.vue` with a compact YanJie brand mark, a desktop-only decision-path visual, responsive layout constraints, and slots for title, subtitle, form and footer. Use regular panels rather than nested decorative cards.

- [x] **Step 3: Verify the shared shell**

Run: `cmd.exe /d /c npm run build`

Expected: PASS.

### Task 2: Upgrade Login Interaction Design

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Test: `frontend` production build

**Interfaces:**
- Consumes: `AuthShell`, `useAuthStore()`, `useRoute()`, and `useRouter()`.
- Produces: login UI preserving `auth.login(identifier, password)` and redirect behavior.

- [x] **Step 1: Write the failing compile check for password visibility state**

Add a `showPassword` ref and bind an icon button to the password input before adding its icon import.

Run: `cmd.exe /d /c npm run build`

Expected: FAIL because the selected icon component is undefined.

- [x] **Step 2: Implement login presentation states**

Use `AuthShell`, add password visibility, clear field hierarchy, contextual error presentation and a visible busy state. Keep the existing submit function and redirect expression unchanged.

- [x] **Step 3: Verify login**

Run: `cmd.exe /d /c npm run build`

Expected: PASS.

### Task 3: Upgrade Registration Interaction Design

**Files:**
- Modify: `frontend/src/views/RegisterView.vue`
- Test: `frontend` production build

**Interfaces:**
- Consumes: `AuthShell` and `useAuthStore()`.
- Produces: registration UI preserving `auth.register(username, password, email)` and navigation to `/`.

- [x] **Step 1: Write the failing compile check for password strength presentation**

Add a computed password strength value referenced by the template before declaring the computed value.

Run: `cmd.exe /d /c npm run build`

Expected: FAIL because `passwordStrength` is not defined.

- [x] **Step 2: Implement registration presentation states**

Use `AuthShell`, add password visibility, a local non-authoritative password-strength indicator, concise field guidance and the existing busy/error treatment.

- [x] **Step 3: Verify registration**

Run: `cmd.exe /d /c npm run build`

Expected: PASS.

### Task 4: Verify Responsive Authentication Workflows

**Files:**
- Verify: `frontend/src/components/auth/AuthShell.vue`
- Verify: `frontend/src/views/LoginView.vue`
- Verify: `frontend/src/views/RegisterView.vue`

- [x] **Step 1: Build the production frontend**

Run: `cmd.exe /d /c npm run build`

Expected: PASS with no TypeScript or Vite errors.

- [x] **Step 2: Inspect desktop and mobile layouts**

Run the Vite server and verify `/login` and `/register` at desktop and mobile viewport widths. Confirm fields, error area, submit action and route links remain fully visible.
