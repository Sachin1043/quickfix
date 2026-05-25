## Test Data Strategy

### How test data is created

I created four factory functions at the top of test_job_card.py:

- create_device_type() — creates Mobile device type if not exists
- create_technician() — creates Test Tech technician if not exists
- create_spare_part() — inserts a fresh spare part with known values
- create_job_card() — inserts a job card with all required fields

All factory functions accept **kwargs so each test can override
any field without writing the full setup again.

### How each test starts clean

setUp() runs before every single test and:
- Calls all four factory functions
- Resets stock_qty to 10 on Test Part

This makes sure no test depends on what the previous test did.
Tests can run in any order and give the same result every time.

### How data is cleaned up

FrappeTestCase wraps each test in a database transaction that is
rolled back automatically after the test finishes. So no test data
stays in the database between tests. The database stays clean
across all 22 tests without any manual cleanup needed.

### Why I did not use static fixtures or CSV files

Static fixture files go outdated when doctypes change. Factory
functions always work with the current doctype structure because
they use frappe.get_doc(). If a required field is added later,
the factory function will fail immediately with a clear error
instead of silently inserting wrong data.