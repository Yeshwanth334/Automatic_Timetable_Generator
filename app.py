from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL
import random
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configurations (replace with your details)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Yeshwanth334'
app.config['MYSQL_DB'] = 'timetable'

mysql = MySQL(app)

# Function to load timeslots from a JSON file
def load_timeslots():
    try:
        with open('timeslots.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading timeslots: {e}")
        return []

# Function to get subjects from the database
def get_subjects_from_database():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, name, periods FROM subjects')
    subjects = cursor.fetchall()
    cursor.close()
    return [{'id': subj[0], 'name': subj[1], 'periods': subj[2]} for subj in subjects]

# Genetic algorithm functions
def generate_individual(subjects, timeslots):
    individual = {}
    all_timeslots = [(slot['day'], period['start_time'], period['end_time'], period.get('lunch_break', False)) for slot in timeslots for period in slot['periods']]

    for subject in subjects:
        available_timeslots = [ts for ts in all_timeslots if not ts[3]]  # Filter out lunch breaks
        random.shuffle(available_timeslots)
        for _ in range(subject['periods']):
            if subject['id'] not in individual:
                individual[subject['id']] = []
            if subject.get('type', 'default') == 'lab' and subject['periods'] >= 2:
                found_consecutive_slots = False
                for i in range(len(available_timeslots) - subject['periods'] + 1):
                    consecutive_slots = available_timeslots[i:i + subject['periods']]
                    consecutive_days = {slot[0] for slot in consecutive_slots}
                    if len(consecutive_days) == 1:
                        start_times = [slot[1] for slot in consecutive_slots]
                        end_times = [slot[2] for slot in consecutive_slots]
                        if start_times == sorted(start_times) and end_times == sorted(end_times):
                            individual[subject['id']].extend(consecutive_slots)
                            found_consecutive_slots = True
                            for slot in consecutive_slots:
                                available_timeslots.remove(slot)
                            break
                if not found_consecutive_slots:
                    timeslot = available_timeslots.pop()
                    individual[subject['id']].append(timeslot)
            else:
                timeslot = available_timeslots.pop()
                individual[subject['id']].append(timeslot)
    return individual

def has_conflict(individual):
    assigned_timeslots = set()
    for times in individual.values():
        for timeslot in times:
            if timeslot in assigned_timeslots:
                return True
            assigned_timeslots.add(timeslot)
    return False

def fitness_function(individual):
    fitness = 0
    if has_conflict(individual):
        fitness -= 10
    return fitness

def selection(population):
    total_fitness = sum(fitness_function(ind) for ind in population)
    probabilities = [fitness_function(ind) / total_fitness for ind in population]
    parent1 = random.choices(population, weights=probabilities)[0]
    parent2 = random.choices(population, weights=probabilities)[0]
    while parent1 == parent2:
        parent2 = random.choices(population, weights=probabilities)[0]
    return parent1, parent2

def crossover(parent1, parent2):
    child = {}
    for key in parent1.keys():
        if key in parent2:
            child[key] = random.choice([parent1[key], parent2[key]])
        else:
            child[key] = parent1[key]
    return child

def mutate(individual, timeslots):
    all_timeslots = [(slot['day'], period['start_time'], period['end_time'], period.get('lunch_break', False)) for slot in timeslots for period in slot['periods']]
    if random.random() < 0.1:
        subject_id = random.choice(list(individual.keys()))
        available_timeslots = [ts for ts in all_timeslots if not ts[3]]  # Filter out lunch breaks
        random.shuffle(available_timeslots)
        timeslot = available_timeslots.pop()
        individual[subject_id] = [(timeslot[0], timeslot[1], timeslot[2])]
    return individual

def genetic_algorithm(subjects, timeslots, population_size, generations):
    population = [generate_individual(subjects, timeslots) for _ in range(population_size)]
    best_individual = population[0]
    for _ in range(generations):
        new_population = []
        for _ in range(population_size // 2):
            parent1, parent2 = selection(population)
            child1 = mutate(crossover(parent1, parent2), timeslots)
            child2 = mutate(crossover(parent1, parent2), timeslots)
            new_population.extend([child1, child2])
        population = sorted(new_population, key=fitness_function, reverse=True)
        best_individual = population[0]
        if fitness_function(best_individual) == 0:
            break
    return best_individual

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate_timetable', methods=['POST'])
def generate_timetable():
    subjects = get_subjects_from_database()
    timeslots = load_timeslots()
    classroom_ids = request.form.getlist('classroom_ids')
    population_size = 50
    generations = 1000
    timetables = {}

    for classroom_id in classroom_ids:
        best_timetable = genetic_algorithm(subjects, timeslots, population_size, generations)
        timetable = {}
        for subject_id, slots in best_timetable.items():
            if subject_id not in timetable:
                timetable[subject_id] = []
            for slot in slots:
                timetable[subject_id].append((slot[0], slot[1], slot[2]))
        timetables[classroom_id] = timetable
    subject_names = {subject['id']: subject['name'] for subject in subjects}
    return render_template('timetable.html', timetables=timetables, timeslots=timeslots, subject_names=subject_names, classroom_ids=classroom_ids)

@app.route('/generate')
def generate():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, room_number FROM classrooms")
    classrooms = cursor.fetchall()
    cursor.close()
    return render_template('generate.html', classrooms=classrooms)

@app.route('/subject', methods=['GET', 'POST'])
def add_subject():
    if request.method == 'POST':
        sub_name = request.form['Subname']
        sub_type = request.form['subjectType']
        sub_code = request.form['Subcode']
        sub_year = request.form['Subyear']
        sub_sem = request.form['Subsem']
        sub_periods = request.form['Subperiods']
        sub_dep = request.form['Subdep']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM subjects WHERE name=%s AND code=%s', (sub_name, sub_code))
        existing_subject = cursor.fetchone()
        if existing_subject:
            flash('Subject already exists', 'danger')
        else:
            cursor.execute('INSERT INTO subjects (name, type, code, year, semester, periods, department) VALUES (%s, %s, %s, %s, %s, %s, %s)', 
                           (sub_name, sub_type, sub_code, sub_year, sub_sem, sub_periods, sub_dep))
            mysql.connection.commit()
            flash('Subject added successfully', 'success')
        cursor.close()
        return redirect(url_for('add_subject'))
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM subjects')
    subjects = cursor.fetchall()
    cursor.close()
    return render_template('Subjectform.html', subjects=subjects)

@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
def delete_subject(subject_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM subjects WHERE id = %s', (subject_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Subject removed successfully', 'success')
    return redirect(url_for('add_subject'))

@app.route('/remove_all_subjects', methods=['POST'])
def remove_all_subjects():
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM subjects')
    mysql.connection.commit()
    cursor.close()
    flash('All subjects removed successfully', 'success')
    return redirect(url_for('add_subject'))

@app.route('/teacher', methods=['GET', 'POST'])
def add_teacher():
    if request.method == 'POST':
        tea_name = request.form['Teaname']
        tea_id = request.form['Teacid']
        tea_dep = request.form['Teadep']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM teachers WHERE name=%s AND teacher_id=%s', (tea_name, tea_id))
        existing_teacher = cursor.fetchone()
        if existing_teacher:
            flash('Teacher already exists', 'danger')
        else:
            cursor.execute('INSERT INTO teachers (name, teacher_id, department) VALUES (%s, %s, %s)', 
                           (tea_name, tea_id, tea_dep))
            mysql.connection.commit()
            flash('Teacher added successfully', 'success')
        cursor.close()
        return redirect(url_for('add_teacher'))
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM teachers')
    teachers = cursor.fetchall()
    cursor.close()
    return render_template('teacherform.html', teachers=teachers)

@app.route('/delete_teacher/<int:teacher_id>', methods=['POST'])
def delete_teacher(teacher_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM teachers WHERE id = %s', (teacher_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Teacher removed successfully', 'success')
    return redirect(url_for('add_teacher'))

@app.route('/remove_all_teachers', methods=['POST'])
def remove_all_teachers():
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM teachers')
    mysql.connection.commit()
    cursor.close()
    flash('All teachers removed successfully', 'success')
    return redirect(url_for('add_teacher'))

@app.route('/classroom', methods=['GET', 'POST'])
def add_classroom():
    if request.method == 'POST':
        class_name = request.form['classname']
        class_type = request.form['ClassType']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM classrooms WHERE room_number=%s AND type=%s', (class_name, class_type))
        existing_classroom = cursor.fetchone()
        if existing_classroom:
            flash('Classroom already exists', 'danger')
        else:
            cursor.execute('INSERT INTO classrooms (room_number, type) VALUES (%s, %s)', 
                           (class_name, class_type))
            mysql.connection.commit()
            flash('Classroom added successfully', 'success')
        cursor.close()
        return redirect(url_for('add_classroom'))
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM classrooms')
    classrooms = cursor.fetchall()
    cursor.close()
    return render_template('classroomform.html', classrooms=classrooms)

@app.route('/delete_classroom/<int:classroom_id>', methods=['POST'])
def delete_classroom(classroom_id):
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM classrooms WHERE id = %s', (classroom_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Classroom removed successfully', 'success')
    return redirect(url_for('add_classroom'))

@app.route('/remove_all_classrooms', methods=['POST'])
def remove_all_classrooms():
    cursor = mysql.connection.cursor()
    cursor.execute('DELETE FROM classrooms')
    mysql.connection.commit()
    cursor.close()
    flash('All classrooms removed successfully', 'success')
    return redirect(url_for('add_classroom'))

@app.route('/allot_classroom', methods=['GET', 'POST'])
def allot_classroom():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, room_number FROM classrooms")
    classrooms = cursor.fetchall()
    if request.method == 'POST':
        section = request.form.get('section')
        classroom_id = request.form.get('classroom_id')
        if section and classroom_id:
            classroom_id = int(classroom_id)
            cursor.execute("SELECT * FROM classroom_allotments WHERE section = %s AND classroom_id = %s", (section, classroom_id))
            existing_allotment = cursor.fetchone()
            if existing_allotment:
                flash('This allotment already exists', 'danger')
            else:
                cursor.execute("INSERT INTO classroom_allotments (section, classroom_id) VALUES (%s, %s)", (section, classroom_id))
                mysql.connection.commit()
                flash('Classroom allotted successfully', 'success')
            return redirect(url_for('allot_classroom'))
        else:
            flash('Invalid section or classroom ID', 'danger')
    cursor.execute("""
        SELECT ca.id, ca.section, c.id AS classroom_id, c.room_number AS classroom_number
        FROM classroom_allotments ca
        JOIN classrooms c ON ca.classroom_id = c.id
    """)
    allotments = cursor.fetchall()
    cursor.close()
    return render_template('allot_classroom.html', classrooms=classrooms, allotments=allotments)

@app.route('/delete_classroomallotment/<int:allotment_id>', methods=['POST'])
def delete_classroomallotment(allotment_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM classroom_allotments WHERE id = %s", (allotment_id,))
    mysql.connection.commit()
    flash('Allotment removed successfully', 'success')
    return redirect(url_for('allot_classroom'))

@app.route('/allot_theory', methods=['GET', 'POST'])
def allot_theory():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, code, name FROM subjects")
    subjects = cursor.fetchall()
    print("Subjects fetched from DB:", subjects)  
    cursor.execute("SELECT id, name FROM teachers")
    teachers = cursor.fetchall()
    print("Teachers fetched from DB:", teachers)
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        teacher_id = request.form.get('teacher_id')
        if subject_id and teacher_id:
            subject_id = int(subject_id)
            teacher_id = int(teacher_id)
            cursor.execute("SELECT * FROM theory_allotments WHERE subject_id = %s AND teacher_id = %s", (subject_id, teacher_id))
            existing_allotment = cursor.fetchone()
            if existing_allotment:
                flash('This allotment already exists', 'danger')
            else:
                cursor.execute("INSERT INTO theory_allotments (subject_id, teacher_id) VALUES (%s, %s)", (subject_id, teacher_id))
                mysql.connection.commit()
                flash('Classroom allotted successfully', 'success')
            return redirect(url_for('allot_theory'))
        else:
            flash('Invalid subject or teacher ID', 'danger')
    cursor.execute("""
        SELECT ta.id, s.code AS subject_code, s.name AS subject_name,
               t.id AS teacher_id, t.name AS teacher_name
        FROM theory_allotments ta
        JOIN subjects s ON ta.subject_id = s.id
        JOIN teachers t ON ta.teacher_id = t.id
    """)
    allotments = cursor.fetchall()
    print("Allotments fetched from DB:", allotments)  # Debug print statement
    cursor.close()
    return render_template('allot_theory.html', subjects=subjects, teachers=teachers, allotments=allotments)

@app.route('/delete_theoryallotment/<int:allotment_id>', methods=['POST'])
def delete_theoryallotment(allotment_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM theory_allotments WHERE id = %s", (allotment_id,))
    mysql.connection.commit()
    flash('Allotment removed successfully', 'success')
    return redirect(url_for('allot_theory'))

@app.route('/allot_lab', methods=['GET', 'POST'])
def allot_lab():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, code, name FROM subjects")
    subjects = cursor.fetchall()
    cursor.execute("SELECT id, name FROM teachers")
    teachers = cursor.fetchall()
    cursor.execute("SELECT id, room_number FROM classrooms")
    classrooms = cursor.fetchall()
    if request.method == 'POST':
        subject_id = request.form.get('subject_id')
        teacher_ids = request.form.getlist('teacher_ids') 
        classroom_id = request.form.get('classroom_id')
        if subject_id and teacher_ids and classroom_id:
            try:
                subject_id = int(subject_id)
                teacher_ids = [int(teacher_id) for teacher_id in teacher_ids]
                classroom_id = int(classroom_id)
            except ValueError:
                flash('Invalid ID format', 'danger')
                return redirect(url_for('allot_lab'))
            for teacher_id in teacher_ids:
                cursor.execute("""
                    SELECT * FROM lab_allotments 
                    WHERE subject_id = %s AND teacher_id = %s AND classroom_id = %s
                """, (subject_id, teacher_id, classroom_id))
                existing_allotment = cursor.fetchone()
                if existing_allotment:
                    flash('Lab allotment already exists for one of the selected teachers', 'danger')
                    return redirect(url_for('allot_lab'))
            for teacher_id in teacher_ids:
                cursor.execute("""
                    INSERT INTO lab_allotments (subject_id, teacher_id, classroom_id) 
                    VALUES (%s, %s, %s)
                """, (subject_id, teacher_id, classroom_id))
            mysql.connection.commit()
            flash('Lab allotted successfully', 'success')
            return redirect(url_for('allot_lab'))
        else:
            flash('Invalid subject, teacher, or classroom ID', 'danger')
    cursor.execute("""
        SELECT la.id, s.code AS subject_code, s.name AS subject_name,
               c.id AS classroom_id, c.room_number AS classroom_number
        FROM lab_allotments la
        JOIN subjects s ON la.subject_id = s.id
        JOIN classrooms c ON la.classroom_id = c.id
    """)
    allotments = cursor.fetchall()
    allotments_with_teachers = []
    for allotment in allotments:
        cursor.execute("""
            SELECT t.id, t.name 
            FROM teachers t
            JOIN lab_allotments la ON t.id = la.teacher_id
            WHERE la.subject_id = %s AND la.classroom_id = %s
        """, (allotment[0], allotment[3]))
        teachers_for_allotment = cursor.fetchall()
        allotments_with_teachers.append((allotment, teachers_for_allotment))
    cursor.close()    
    return render_template('allot_lab.html', subjects=subjects, teachers=teachers, classrooms=classrooms, allotments=allotments_with_teachers)

@app.route('/delete_laballotment/<int:allotment_id>', methods=['POST'])
def delete_laboutment(allotment_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM lab_allotments WHERE id = %s", (allotment_id,))
    mysql.connection.commit()
    cursor.close()
    flash('Lab allotment removed successfully', 'success')
    return redirect(url_for('allot_lab'))

if __name__ == "__main__":
    app.run(debug=True)