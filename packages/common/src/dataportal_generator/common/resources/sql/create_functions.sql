CREATE OR REPLACE FUNCTION insert_termcode(
    p_system  TEXT,
    p_code    TEXT,
    p_version TEXT,
    p_display TEXT
) RETURNS INTEGER AS $$
DECLARE
    termcode_id INTEGER;
BEGIN
    -- Attempt to insert the new record
    INSERT INTO termcode (system, code, version, display)
    VALUES (p_system, p_code, p_version, p_display)
    RETURNING id INTO termcode_id;

    -- If insertion is successful, return the new termcode ID
    RETURN termcode_id;
EXCEPTION
    WHEN unique_violation THEN
        -- Handle the unique constraint violation
        -- Find the conflicting record's ID
        SELECT id INTO termcode_id
        FROM termcode
        WHERE system = p_system
          AND code = p_code
          AND (version IS NOT DISTINCT FROM p_version);

        -- Return the existing termcode ID
        RETURN termcode_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION insert_context(
    p_system  TEXT,
    p_code    TEXT,
    p_version TEXT,
    p_display TEXT
) RETURNS INTEGER AS $$
DECLARE
    context_id INTEGER;
BEGIN
    -- Attempt to insert the new record
    INSERT INTO context (system, code, version, display)
    VALUES (p_system, p_code, p_version, p_display)
    RETURNING id INTO context_id;

    -- If insertion is successful, return the new context ID
    RETURN context_id;
EXCEPTION
    WHEN unique_violation THEN
        -- Handle the unique constraint violation
        -- Find the conflicting record's ID
        SELECT id INTO context_id
        FROM context
        WHERE system = p_system
          AND code = p_code
          AND (version IS NOT DISTINCT FROM p_version);

        -- Return the existing termcode ID
        RETURN context_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION insert_uiprofile(
    p_name  TEXT,
    p_ui_profile    JSON
) RETURNS INTEGER AS $$
DECLARE
    uiprofile_id INTEGER;
BEGIN
    -- Attempt to insert the new record
    INSERT INTO ui_profile (name, ui_profile)
    VALUES (p_name, p_ui_profile)
    RETURNING id INTO uiprofile_id;

    -- If insertion is successful, return the new ui profile ID
    RETURN uiprofile_id;
EXCEPTION
    WHEN unique_violation THEN
        -- Handle the unique constraint violation
        -- Find the conflicting record's ID
        SELECT id INTO uiprofile_id
        FROM ui_profile
        WHERE name = p_name;

        -- Return the existing termcode ID
        RETURN uiprofile_id;
END;
$$ LANGUAGE plpgsql;
