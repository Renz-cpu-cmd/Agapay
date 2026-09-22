class Account {
  const Account({
    required this.id,
    required this.name,
    required this.email,
    required this.phone,
    required this.barangay,
    required this.role,
    required this.createdAt,
  });
  final int id;
  final String name, email, phone, barangay, role;
  final DateTime createdAt;

  factory Account.fromJson(Map<String, dynamic> value) => Account(
    id: value['id'] as int,
    name: value['name'] as String,
    email: value['email'] as String,
    phone: value['phone'] as String,
    barangay: value['barangay'] as String,
    role: value['role'] as String,
    createdAt: DateTime.parse(value['created_at'] as String),
  );
}
