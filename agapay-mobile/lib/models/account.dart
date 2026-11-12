class Account {
  const Account({
    required this.id,
    required this.version,
    this.emailVerifiedAt,
    required this.name,
    required this.email,
    required this.phone,
    required this.barangay,
    required this.role,
    required this.createdAt,
  });
  final int id, version;
  final DateTime? emailVerifiedAt;
  final String name, email, phone, barangay, role;
  final DateTime createdAt;

  factory Account.fromJson(Map<String, dynamic> value) => Account(
    id: value['id'] as int,
    version: value['version'] as int? ?? 1,
    emailVerifiedAt: DateTime.tryParse(
      value['email_verified_at'] as String? ?? '',
    ),
    name: value['name'] as String,
    email: value['email'] as String,
    phone: value['phone'] as String,
    barangay: value['barangay'] as String,
    role: value['role'] as String,
    createdAt: DateTime.parse(value['created_at'] as String),
  );
}
