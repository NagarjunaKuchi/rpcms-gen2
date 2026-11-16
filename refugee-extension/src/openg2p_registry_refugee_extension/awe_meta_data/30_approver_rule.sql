-- Individual approver rules.
INSERT INTO "public"."approver_rule" ("id","stage_id","rule_type","rule_value","kind","required","created_at","updated_at") VALUES
    ('d1000000-0000-4000-8000-000000000101', 'b1000000-0000-4000-8000-000000000101', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000102', 'b1000000-0000-4000-8000-000000000102', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000111', 'b1000000-0000-4000-8000-000000000111', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000112', 'b1000000-0000-4000-8000-000000000112', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Household approver rules (best-effort).
INSERT INTO "public"."approver_rule" ("id","stage_id","rule_type","rule_value","kind","required","created_at","updated_at") VALUES
    ('d1000000-0000-4000-8000-000000000201', 'b1000000-0000-4000-8000-000000000201', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000202', 'b1000000-0000-4000-8000-000000000202', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000121', 'b1000000-0000-4000-8000-000000000121', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000122', 'b1000000-0000-4000-8000-000000000122', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Partner approver rules.
INSERT INTO "public"."approver_rule" ("id","stage_id","rule_type","rule_value","kind","required","created_at","updated_at") VALUES
    ('d1000000-0000-4000-8000-000000000301', 'b1000000-0000-4000-8000-000000000301', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000302', 'b1000000-0000-4000-8000-000000000302', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000131', 'b1000000-0000-4000-8000-000000000131', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000132', 'b1000000-0000-4000-8000-000000000132', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT DO NOTHING;

-- Project approver rules.
INSERT INTO "public"."approver_rule" ("id","stage_id","rule_type","rule_value","kind","required","created_at","updated_at") VALUES
    ('d1000000-0000-4000-8000-000000000401', 'b1000000-0000-4000-8000-000000000401', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000402', 'b1000000-0000-4000-8000-000000000402', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000141', 'b1000000-0000-4000-8000-000000000141', 'user', '{"user_id": "alex.carter"}', 'approver', 'FALSE', NOW(), NOW()),
    ('d1000000-0000-4000-8000-000000000142', 'b1000000-0000-4000-8000-000000000142', 'user', '{"user_id": "nina.patel"}', 'approver', 'FALSE', NOW(), NOW())
ON CONFLICT DO NOTHING;
