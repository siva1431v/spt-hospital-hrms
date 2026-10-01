import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('SPT Hospital HRMS - Smoke Test Suite', () => {

  test('1. Authentication: Login flow', async ({ page }) => {
    await page.goto('/login');
    await expect(page).toHaveTitle(/SPT Hospital HRMS/);

    // Fill credentials
    await page.fill('#username', 'admin');
    await page.fill('#password', 'Admin@123');
    await page.click('button[type="submit"]');

    // Wait for redirect to dashboard
    await page.waitForURL('**/dashboard');
    await expect(page.getByRole('heading', { name: 'Hospital Overview' })).toBeVisible();
    await expect(page.locator('text=Total Employees')).toBeVisible();
  });

  test('2. Navigation: Sidebar single active state on each route', async ({ page }) => {
    // Log in first
    await page.goto('/login');
    await page.fill('#username', 'admin');
    await page.fill('#password', 'Admin@123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    const testRoutes = [
      { route: '/dashboard', expectedActiveHref: '/dashboard', label: 'Dashboard' },
      { route: '/attendance', expectedActiveHref: '/attendance', label: 'Daily Attendance' },
      { route: '/attendance/monthly', expectedActiveHref: '/attendance/monthly', label: 'Monthly Summary' },
      { route: '/settings/users', expectedActiveHref: '/settings/users', label: 'Users' },
      { route: '/payroll/salary-slips', expectedActiveHref: '/payroll/salary-slips', label: 'Salary Slips' },
    ];

    for (const { route, expectedActiveHref, label } of testRoutes) {
      await page.goto(route);
      await page.waitForLoadState('networkidle');

      // Locate all active navigation links in sidebar
      const activeLinks = page.locator('aside nav a.bg-teal-600');
      
      // Verify exactly ONE item is active
      const count = await activeLinks.count();
      expect(count, `Expected exactly 1 active link on ${route} but found ${count}`).toBe(1);

      // Verify the active link has the exact expected href
      const activeHref = await activeLinks.first().getAttribute('href');
      expect(activeHref, `On route ${route}, expected active link ${expectedActiveHref} for ${label} but got ${activeHref}`).toBe(expectedActiveHref);
    }
  });

  test('3. Administration: User create, search, and edit', async ({ page }) => {
    // Log in as super admin
    await page.goto('/login');
    await page.fill('#username', 'admin');
    await page.fill('#password', 'Admin@123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    await page.goto('/settings/users');
    await page.waitForLoadState('networkidle');

    const uniqueId = Date.now().toString().slice(-6);
    const newUsername = `smoke_u_${uniqueId}`;
    const newEmail = `smoke_${uniqueId}@spthospital.com`;
    const initialName = `Smoke Doctor ${uniqueId}`;
    const updatedName = `Dr. Smoke Updated ${uniqueId}`;

    // 1. Create User
    await page.click('button:has-text("Add New User")');
    await expect(page.locator('text=Add New Hospital User')).toBeVisible();

    await page.fill('input[placeholder="e.g. Dr. Ramesh Kumar"]', initialName);
    await page.fill('input[placeholder="e.g. ramesh"]', newUsername);
    await page.fill('input[placeholder="Min. 8 characters"]', 'SecurePass123!');
    await page.fill('input[placeholder="ramesh@spthospital.com"]', newEmail);
    await page.click('button:has-text("Create Account")');

    // Wait for user to appear in table
    const table = page.locator('table');
    await page.waitForSelector(`tbody tr:has-text("${newUsername}")`, { timeout: 10000 });
    await expect(table.locator(`text=${initialName}`)).toBeVisible();

    // 2. Search User
    const searchInput = page.locator('input[placeholder*="Search users"]');
    await searchInput.fill(newUsername);
    await page.waitForTimeout(400); // debounce/filtering
    const userRow = page.locator('tbody tr', { hasText: newUsername });
    await expect(userRow).toBeVisible();

    // 3. Edit User
    await userRow.locator('button:has-text("Edit")').click();
    await expect(page.locator('text=Edit User: @' + newUsername)).toBeVisible();

    // Update Full Name
    const nameInput = page.locator('div[role="dialog"] input[value="' + initialName + '"]');
    await nameInput.fill(updatedName);
    await page.click('button:has-text("Save Changes")');

    // Verify updated full name appears in table
    await page.waitForSelector(`tbody tr:has-text("${updatedName}")`, { timeout: 10000 });
    await expect(page.locator('tbody tr', { hasText: updatedName })).toBeVisible();

    // Clean up: delete user
    const updatedRow = page.locator('tbody tr', { hasText: newUsername });
    await updatedRow.locator('button:has-text("Delete")').click();
    await page.click('div[role="dialog"] button:has-text("Confirm Delete")');
    await page.waitForTimeout(500);
  });

  test('4. Attendance: Duplicate PDF import rejection and detection', async ({ page }) => {
    // Log in
    await page.goto('/login');
    await page.fill('#username', 'admin');
    await page.fill('#password', 'Admin@123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    await page.goto('/attendance/import');
    await page.waitForLoadState('networkidle');

    // Fixture PDF path (frontend/tests -> backend/tests/fixtures)
    const pdfPath = path.resolve(__dirname, '../../backend/tests/fixtures/Monthly_Status_Report_Aug_1_to_24.pdf');

    // Upload file directly to file input
    await page.locator('#pdf-upload-input').setInputFiles(pdfPath);

    // Wait for file to be recognized
    await expect(page.getByText('Monthly_Status_Report_Aug_1_to_24.pdf', { exact: true })).toBeVisible();

    // Click Preview Import
    await page.click('button:has-text("Preview Import")');

    // Wait for Step 3 Preview
    await page.waitForSelector('text=Report Metadata & Summary', { timeout: 30000 });

    // Assert duplicate detection indicators
    const hasDuplicateBanner = await page.locator('text=Exact File Previously Imported').isVisible().catch(() => false);
    const hasDuplicatesCount = await page.locator('text=Duplicates Detected').isVisible().catch(() => false);
    const hasDuplicateStrategy = await page.locator('text=Duplicate Handling Strategy').isVisible().catch(() => false);

    expect(hasDuplicateBanner || hasDuplicatesCount || hasDuplicateStrategy).toBeTruthy();
  });

  test('5. Viewport Layout: Tables Actions columns visible without horizontal overflow at 1280px', async ({ page }) => {
    // Explicitly set 1280px wide viewport
    await page.setViewportSize({ width: 1280, height: 800 });

    // Log in
    await page.goto('/login');
    await page.fill('#username', 'admin');
    await page.fill('#password', 'Admin@123');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/dashboard');

    const tablePages = [
      { url: '/employees', label: 'Employees' },
      { url: '/attendance', label: 'Daily Attendance' },
      { url: '/attendance/import-history', label: 'Import History' },
      { url: '/attendance/exceptions', label: 'Exceptions' },
    ];

    for (const { url, label } of tablePages) {
      await page.goto(url);
      await page.waitForLoadState('networkidle');

      // Find the Actions header
      const actionsHeader = page.locator('th:has-text("Action")').first();
      await expect(actionsHeader, `${label} table should have an Actions column header`).toBeVisible();

      // Check the bounding box of the Actions column header
      const box = await actionsHeader.boundingBox();
      expect(box, `${label} Actions column header should have a valid bounding box`).not.toBeNull();
      if (box) {
        // Assert it is completely inside the 1280px viewport
        expect(
          box.x + box.width,
          `${label} Actions column right edge (${box.x + box.width}px) should not exceed viewport width (1280px)`
        ).toBeLessThanOrEqual(1280);
        expect(
          box.x,
          `${label} Actions column left edge (${box.x}px) should be within visible screen`
        ).toBeGreaterThanOrEqual(0);
      }

      // If rows exist, check that the actions cell in the first row is also visible
      const actionsCell = page.locator('td.sticky.right-0, td:has(button)').first();
      if (await actionsCell.isVisible()) {
        const cellBox = await actionsCell.boundingBox();
        expect(cellBox).not.toBeNull();
        if (cellBox) {
          expect(
            cellBox.x + cellBox.width,
            `${label} Actions cell right edge (${cellBox.x + cellBox.width}px) should not exceed viewport width (1280px)`
          ).toBeLessThanOrEqual(1280);
        }
      }
    }
  });

});
