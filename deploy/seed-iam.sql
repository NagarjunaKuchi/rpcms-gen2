-- IAM seed for the RPCMS dev stack (login provider + RBAC for registry-staff-portal).
-- Extracted from OpenG2P/registry-platform functional-testing/docker/run-compose-gate.sh (MPL-2.0).
-- Idempotent. Run as iam_service_user against database iam_service.

INSERT INTO login_providers (
        provider_name, client_id, client_secret,
        token_endpoint_auth_method, issuer,
        server_metadata_url, jwks_uri,
        authorization_endpoint, token_endpoint, userinfo_endpoint,
        oauth_callback_url, scope, active, created_at
      ) SELECT
        'Keycloak', 'registry-staff-portal', 'func-gate-client-secret',
        'client_secret_post', 'http://keycloak:8080/realms/staff',
        'http://keycloak:8080/realms/staff/.well-known/openid-configuration',
        'http://keycloak:8080/realms/staff/protocol/openid-connect/certs',
        'http://keycloak:8080/realms/staff/protocol/openid-connect/auth',
        'http://keycloak:8080/realms/staff/protocol/openid-connect/token',
        'http://keycloak:8080/realms/staff/protocol/openid-connect/userinfo',
        'http://localhost:18081/auth/callback',
        'openid profile email', true, NOW()
      WHERE NOT EXISTS (SELECT 1 FROM login_providers WHERE issuer = 'http://keycloak:8080/realms/staff');

INSERT INTO staff_portal_applications
      (id, application_mnemonic, application_description, active, is_self_registered, created_at, updated_at)
    SELECT 100, 'registry-staff-portal', 'Registry Platform', true, true, NOW(), NOW()
    WHERE NOT EXISTS (
      SELECT 1 FROM staff_portal_applications WHERE application_mnemonic = 'registry-staff-portal'
    );

    INSERT INTO staff_application_permissions (id, application_id, permission_mnemonic, permission_description, active, created_at, updated_at)
    VALUES
      (100, 100, 'intakeFormDefinition:view',      'intakeFormDefinition:view',      true, NOW(), NOW()),
      (101, 100, 'intakeFormDefinition:edit',      'intakeFormDefinition:edit',      true, NOW(), NOW()),
      (102, 100, 'intakeSubmission:view',          'intakeSubmission:view',          true, NOW(), NOW()),
      (103, 100, 'intakeSubmission:edit',          'intakeSubmission:edit',          true, NOW(), NOW()),
      (104, 100, 'intakeSubmission:approve',       'intakeSubmission:approve',       true, NOW(), NOW()),
      (105, 100, 'register:view',                  'register:view',                  true, NOW(), NOW()),
      (106, 100, 'register:export',                'register:export',                true, NOW(), NOW()),
      (107, 100, 'register:authenticate',          'register:authenticate',          true, NOW(), NOW()),
      (108, 100, 'registerHistory:view',           'registerHistory:view',           true, NOW(), NOW()),
      (109, 100, 'registerSection:view',           'registerSection:view',           true, NOW(), NOW()),
      (110, 100, 'registerSection:create',         'registerSection:create',         true, NOW(), NOW()),
      (111, 100, 'registerSection:edit',           'registerSection:edit',           true, NOW(), NOW()),
      (112, 100, 'registerSection:delete',         'registerSection:delete',         true, NOW(), NOW()),
      (113, 100, 'registerDefinition:view',        'registerDefinition:view',        true, NOW(), NOW()),
      (114, 100, 'registerDefinition:create',      'registerDefinition:create',      true, NOW(), NOW()),
      (115, 100, 'registerDefinition:edit',        'registerDefinition:edit',        true, NOW(), NOW()),
      (116, 100, 'registerDefinition:delete',      'registerDefinition:delete',      true, NOW(), NOW()),
      (117, 100, 'registerTab:view',               'registerTab:view',               true, NOW(), NOW()),
      (118, 100, 'registerTab:create',             'registerTab:create',             true, NOW(), NOW()),
      (119, 100, 'registerTab:edit',               'registerTab:edit',               true, NOW(), NOW()),
      (120, 100, 'registerTab:delete',             'registerTab:delete',             true, NOW(), NOW()),
      (121, 100, 'registerScore:view',             'registerScore:view',             true, NOW(), NOW()),
      (122, 100, 'registerScore:create',           'registerScore:create',           true, NOW(), NOW()),
      (123, 100, 'registerScore:edit',             'registerScore:edit',             true, NOW(), NOW()),
      (124, 100, 'registryConfiguration:edit',     'registryConfiguration:edit',     true, NOW(), NOW()),
      (160, 100, 'registryConfiguration:view',     'registryConfiguration:view',     true, NOW(), NOW()),
      (125, 100, 'changeRequest:view',             'changeRequest:view',             true, NOW(), NOW()),
      (126, 100, 'changeRequest:create',           'changeRequest:create',           true, NOW(), NOW()),
      (127, 100, 'changeRequest:approve',          'changeRequest:approve',          true, NOW(), NOW()),
      (128, 100, 'verificationChangeRequest:view', 'verificationChangeRequest:view', true, NOW(), NOW()),
      (129, 100, 'verificationChangeRequest:create','verificationChangeRequest:create',true,NOW(), NOW()),
      (130, 100, 'verificationIntakeForm:view',    'verificationIntakeForm:view',    true, NOW(), NOW()),
      (131, 100, 'verificationIntakeForm:create',  'verificationIntakeForm:create',  true, NOW(), NOW()),
      (132, 100, 'dataModel:view',                 'dataModel:view',                 true, NOW(), NOW()),
      (133, 100, 'dataModel:create',               'dataModel:create',               true, NOW(), NOW()),
      (134, 100, 'dataModel:edit',                 'dataModel:edit',                 true, NOW(), NOW()),
      (135, 100, 'dataModel:delete',               'dataModel:delete',               true, NOW(), NOW()),
      (136, 100, 'ingestKeyPath:view',             'ingestKeyPath:view',             true, NOW(), NOW()),
      (137, 100, 'ingestKeyPath:create',           'ingestKeyPath:create',           true, NOW(), NOW()),
      (138, 100, 'ingestKeyPath:edit',             'ingestKeyPath:edit',             true, NOW(), NOW()),
      (139, 100, 'ingestKeyPath:delete',           'ingestKeyPath:delete',           true, NOW(), NOW()),
      (140, 100, 'ingestExpression:view',          'ingestExpression:view',          true, NOW(), NOW()),
      (141, 100, 'ingestExpression:create',        'ingestExpression:create',        true, NOW(), NOW()),
      (142, 100, 'ingestExpression:edit',          'ingestExpression:edit',          true, NOW(), NOW()),
      (143, 100, 'ingestExpression:delete',        'ingestExpression:delete',        true, NOW(), NOW()),
      (144, 100, 'ingestTemplate:view',            'ingestTemplate:view',            true, NOW(), NOW()),
      (145, 100, 'ingestTemplate:create',          'ingestTemplate:create',          true, NOW(), NOW()),
      (146, 100, 'ingestTemplate:edit',            'ingestTemplate:edit',            true, NOW(), NOW()),
      (147, 100, 'ingestTemplate:delete',          'ingestTemplate:delete',          true, NOW(), NOW()),
      (148, 100, 'ingestSubscription:view',        'ingestSubscription:view',        true, NOW(), NOW()),
      (149, 100, 'ingestSubscription:create',      'ingestSubscription:create',      true, NOW(), NOW()),
      (150, 100, 'outgestTopic:view',              'outgestTopic:view',              true, NOW(), NOW()),
      (151, 100, 'outgestTopic:create',            'outgestTopic:create',            true, NOW(), NOW()),
      (152, 100, 'outgestTopic:edit',              'outgestTopic:edit',              true, NOW(), NOW()),
      (153, 100, 'outgestTopic:delete',            'outgestTopic:delete',            true, NOW(), NOW()),
      (154, 100, 'outgestTemplate:view',           'outgestTemplate:view',           true, NOW(), NOW()),
      (155, 100, 'outgestTemplate:create',         'outgestTemplate:create',         true, NOW(), NOW()),
      (156, 100, 'outgestTemplate:edit',           'outgestTemplate:edit',           true, NOW(), NOW()),
      (157, 100, 'outgestTemplate:delete',         'outgestTemplate:delete',         true, NOW(), NOW()),
      (158, 100, 'outgoingMessage:view',           'outgoingMessage:view',           true, NOW(), NOW()),
      (159, 100, 'incomingMessage:view',           'incomingMessage:view',           true, NOW(), NOW()),
      (200, 100, 'rpcmsReport:view',               'rpcmsReport:view',               true, NOW(), NOW()),
      (201, 100, 'rpcmsReport:submit',             'rpcmsReport:submit',             true, NOW(), NOW()),
      (202, 100, 'rpcmsHandover:sync',             'rpcmsHandover:sync',             true, NOW(), NOW()),
      (203, 100, 'rpcmsJobs:run',                  'rpcmsJobs:run',                  true, NOW(), NOW()),
      (204, 100, 'rpcmsReferral:view',             'rpcmsReferral:view',             true, NOW(), NOW()),
      (205, 100, 'rpcmsReferral:review',           'rpcmsReferral:review',           true, NOW(), NOW()),
      (206, 100, 'rpcmsReport:approve',            'rpcmsReport:approve',            true, NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO staff_roles (id, application_id, role_mnemonic, role_description, active, created_at, updated_at)
    VALUES
      (100, 100, 'Operations Administrator', 'Operations Administrator', true, NOW(), NOW()),
      (101, 100, 'Technical Administrator',  'Technical Administrator',  true, NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO staff_role_permissions (role_id, permission_id, active, created_at, updated_at)
    SELECT r.id, p.id, true, NOW(), NOW()
    FROM staff_roles r
    CROSS JOIN staff_application_permissions p
    WHERE r.application_id = 100
      AND p.application_id = 100
    ON CONFLICT DO NOTHING;
