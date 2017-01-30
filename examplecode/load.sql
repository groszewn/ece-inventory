\COPY Users(u_id, name, phone, email, password) FROM 'data/Users.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Professor(u_id, name, phone, email, password) FROM 'data/Professor.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Student(u_id, name, phone, email, password, first_major, second_major, grad_year) FROM 'data/Student.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Groups(group_name, g_id) FROM 'data/Groups.dat' WITH DELIMITER ',' NULL '' CSV
\COPY MemberOf(u_id, g_id, is_leader) FROM 'data/MemberOf.dat' WITH DELIMITER ',' NULL '' CSV
\COPY University(university_name, university_location) FROM 'data/University.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Course(course_code, course_semester, university_name, university_location, course_name, course_pre) FROM 'data/Class.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Section(section_id, section_number, course_code, course_semester, university_name, university_location) FROM 'data/Section.dat' WITH DELIMITER ',' NULL '' CSV
\COPY RegisteredWith(u_id, section_id) FROM 'data/RegisteredWith.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Add(j_id, g_id, message, approved, sent_by, sent_to) FROM 'data/Add.dat' WITH DELIMITER ',' NULL '' CSV
\COPY ProjectAssignment(assignment_id, date_assigned, date_due, description) FROM 'data/ProjectAssignment.dat' WITH DELIMITER ',' NULL '' CSV
\COPY AssignedTo(assignment_id, section_id) FROM 'data/AssignedTo.dat' WITH DELIMITER ',' NULL '' CSV
\COPY Post(post_id, assignment_id, section_id, u_id, post_type, message, time_posted) FROM 'data/Post.dat' WITH DELIMITER ',' NULL '' CSV
\COPY ProjectGroup(g_id, name) FROM 'data/ProjectGroup.dat' WITH DELIMITER ',' NULL '' CSV
\COPY StudyGroup(g_id, name) FROM 'data/StudyGroup.dat' WITH DELIMITER ',' NULL '' CSV
\COPY WorkingOn(g_id, assignment_id) FROM 'data/WorkingOn.dat' WITH DELIMITER ',' NULL '' CSV
\COPY StudyingFor(g_id, section_id) FROM 'data/StudyingFor.dat' WITH DELIMITER ',' NULL '' CSV
\COPY GroupResponse(post_id, g_id, section_id, time_posted, message, approved) FROM 'data/GroupResponse.dat' WITH DELIMITER ',' NULL '' CSV
\COPY UserResponse(post_id, u_id, section_id, time_posted, message, approved) FROM 'data/UserResponse.dat' WITH DELIMITER ',' NULL '' CSV
