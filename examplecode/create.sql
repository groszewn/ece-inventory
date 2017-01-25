CREATE TABLE Users
(u_id INTEGER NOT NULL PRIMARY KEY,
 name VARCHAR(256) NOT NULL,
 phone VARCHAR(15) NOT NULL,
 email VARCHAR(256) NOT NULL,
 password VARCHAR(256) NOT NULL
);

CREATE TABLE Professor
(u_id INTEGER NOT NULL UNIQUE PRIMARY KEY REFERENCES Users(u_id),
 name VARCHAR(256) NOT NULL,
 phone VARCHAR(15) NOT NULL,
 email VARCHAR(256) NOT NULL,
 password VARCHAR(256) NOT NULL
);

CREATE TABLE Student
(u_id INTEGER NOT NULL UNIQUE PRIMARY KEY REFERENCES Users(u_id),
 name VARCHAR(256) NOT NULL,
 phone VARCHAR(15) NOT NULL,
 email VARCHAR(256) NOT NULL,
 password VARCHAR(256) NOT NULL,
 first_major VARCHAR(256), 
 second_major VARCHAR(256),
 grad_year INTEGER CHECK (grad_year > 0)
);

CREATE TABLE Groups
(group_name VARCHAR(256) NOT NULL,
g_id INTEGER NOT NULL UNIQUE PRIMARY KEY
);

CREATE TABLE MemberOf
(u_id INTEGER NOT NULL REFERENCES Users(u_id),
 g_id INTEGER NOT NULL REFERENCES Groups(g_id),
 is_leader CHAR(3) NOT NULL CHECK (is_leader IN ('yes', 'no')),
 PRIMARY KEY (u_id,g_id)
);

CREATE TABLE University
(university_name VARCHAR(265) NOT NULL UNIQUE,
 university_location VARCHAR(265) NOT NULL,
 PRIMARY KEY (university_name, university_location)
);

CREATE TABLE Course
(course_code VARCHAR(256) NOT NULL,
 course_semester VARCHAR(256) NOT NULL,
 university_name VARCHAR(256) NOT NULL,
 university_location VARCHAR(256) NOT NULL,
 course_name VARCHAR(256) NOT NULL,
 course_pre VARCHAR(256) NOT NULL,
 PRIMARY KEY (course_code,course_semester,university_name,university_location),
FOREIGN KEY (university_name, university_location) REFERENCES University (university_name, university_location)
);

CREATE TABLE Section
(section_id INTEGER NOT NULL PRIMARY KEY,
 section_number INTEGER NOT NULL,
 course_code     VARCHAR(256) NOT NULL,
 course_semester VARCHAR(256) NOT NULL,
 university_name VARCHAR(256) NOT NULL,
 university_location VARCHAR(256) NOT NULL,
FOREIGN KEY (course_code, course_semester, university_name, university_location) REFERENCES Course (course_code, course_semester, university_name, university_location)
);

CREATE TABLE RegisteredWith
(u_id INTEGER NOT NULL REFERENCES Users(u_id),
 section_id INTEGER NOT NULL,
 PRIMARY KEY (u_id,section_id),
FOREIGN KEY (section_id) REFERENCES Section (section_id)
);

CREATE TABLE Add 
(j_id INTEGER NOT NULL PRIMARY KEY,
 g_id INTEGER REFERENCES Groups(g_id),
 message VARCHAR(1000),
 approved CHAR(3) NOT NULL CHECK (approved IN ('yes', 'no')),
 sent_to INTEGER REFERENCES Users(u_id),
 sent_by INTEGER REFERENCES Users(u_id)
);

CREATE TABLE ProjectAssignment
(assignment_id INTEGER NOT NULL PRIMARY KEY,
 date_assigned VARCHAR(20),
 date_due VARCHAR(20),
 description VARCHAR(1000)
);

CREATE TABLE AssignedTo 
(assignment_id INTEGER NOT NULL REFERENCES ProjectAssignment(assignment_id),
 section_id INTEGER NOT NULL,
 PRIMARY KEY (assignment_id,section_id),
FOREIGN KEY (section_id)
REFERENCES Section (section_id)
);

CREATE TABLE Post
(post_id INTEGER NOT NULL PRIMARY KEY,
 assignment_id INTEGER NOT NULL REFERENCES ProjectAssignment(assignment_id),
 section_id INTEGER NOT NULL REFERENCES Section(section_id),
 u_id INTEGER NOT NULL REFERENCES Users(u_id),
 post_type VARCHAR(12) NOT NULL CHECK (post_type IN ('need_team', 'need_member')),
 message VARCHAR(100) NOT NULL,
 time_posted VARCHAR(100) NOT NULL
);

CREATE TABLE ProjectGroup
(g_id INTEGER NOT NULL PRIMARY KEY REFERENCES Groups(g_id),
 name VARCHAR(256) NOT NULL
);

CREATE TABLE StudyGroup
(g_id INTEGER NOT NULL PRIMARY KEY REFERENCES Groups(g_id),
 name VARCHAR(256) NOT NULL
);

CREATE TABLE WorkingOn
(g_id INTEGER NOT NULL REFERENCES ProjectGroup(g_id),
 assignment_id INTEGER NOT NULL REFERENCES ProjectAssignment(assignment_id),
 PRIMARY KEY (g_id, assignment_id)
);

CREATE TABLE StudyingFor 
(g_id INTEGER NOT NULL REFERENCES Groups(g_id),
 section_id INTEGER NOT NULL REFERENCES Section(section_id),
 PRIMARY KEY (g_id,section_id),
 FOREIGN KEY (section_id)
 REFERENCES Section(section_id)
);

CREATE TABLE GroupResponse
(post_id INTEGER NOT NULL REFERENCES Post(post_id),
 g_id INTEGER NOT NULL REFERENCES Groups(g_id),
 section_id INTEGER NOT NULL REFERENCES Section(section_id),
 time_posted VARCHAR(100) NOT NULL,
 message VARCHAR(1000),
 approved BOOLEAN NOT NULL,
 PRIMARY KEY (post_id, g_id)
);

CREATE TABLE UserResponse
(post_id INTEGER NOT NULL REFERENCES Post(post_id),
 u_id INTEGER NOT NULL REFERENCES Users(u_id),
 section_id INTEGER NOT NULL REFERENCES Section(section_id),
 time_posted VARCHAR(100) NOT NULL,
 message VARCHAR(1000),
 approved BOOLEAN NOT NULL,
 PRIMARY KEY (post_id, u_id)
);
