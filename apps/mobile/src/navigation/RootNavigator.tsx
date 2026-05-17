import { Ionicons } from "@expo/vector-icons";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";

import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette } from "@/theme";
import { AddItemScreen } from "@/screens/Closet/AddItemScreen";
import { ClosetScreen } from "@/screens/Closet/ClosetScreen";
import { GapsScreen } from "@/screens/Closet/GapsScreen";
import { ItemDetailScreen } from "@/screens/Closet/ItemDetailScreen";
import { FamilyScreen } from "@/screens/Family/FamilyScreen";
import { AddMemberScreen } from "@/screens/Family/AddMemberScreen";
import { SignInScreen } from "@/screens/Auth/SignInScreen";
import { StyleScreen } from "@/screens/Style/StyleScreen";
import { OutfitDetailScreen } from "@/screens/Style/OutfitDetailScreen";
import { BasePhotoScreen } from "@/screens/You/BasePhotoScreen";
import { StylePreferenceScreen } from "@/screens/You/StylePreferenceScreen";
import { YouScreen } from "@/screens/You/YouScreen";

export type RootStackParamList = {
  Tabs: undefined;
  AddItem: undefined;
  ItemDetail: { itemId: string };
  AddMember: undefined;
  OutfitDetail: { outfitId: string };
  SignIn: undefined;
  Gaps: undefined;
  BasePhoto: undefined;
  StylePreference: undefined;
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator<RootStackParamList>();

/**
 * Tab icons use Ionicons — a single icon family for consistency, outlined
 * when inactive and filled when active (iOS-native convention).
 * All four icons are gender-neutral and minimal.
 */
type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

const TAB_ICONS: Record<string, { outline: IoniconName; filled: IoniconName }> = {
  Closet: { outline: "shirt-outline", filled: "shirt" },
  Style: { outline: "sparkles-outline", filled: "sparkles" },
  Family: { outline: "people-outline", filled: "people" },
  You: { outline: "person-outline", filled: "person" },
};

function Tabs() {
  const isKidMode = useActiveProfile((s) => s.isKidMode);
  const activeColor = isKidMode ? palette.kidPrimary : palette.accent;
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: activeColor,
        tabBarInactiveTintColor: palette.textMuted,
        tabBarStyle: {
          backgroundColor: palette.background,
          borderTopColor: palette.surfaceAlt,
          height: 84,
          paddingTop: 8,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: "600", letterSpacing: 0.3 },
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name];
          if (!icons) return null;
          return (
            <Ionicons
              name={focused ? icons.filled : icons.outline}
              size={size ?? 24}
              color={color}
            />
          );
        },
      })}
    >
      <Tab.Screen name="Closet" component={ClosetScreen} />
      <Tab.Screen name="Style" component={StyleScreen} />
      <Tab.Screen name="Family" component={FamilyScreen} />
      <Tab.Screen name="You" component={YouScreen} />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  const signedIn = useAuth((s) => s.session !== null);
  return (
    <Stack.Navigator
      screenOptions={{
        contentStyle: { backgroundColor: palette.background },
        headerStyle: { backgroundColor: palette.background },
        headerTintColor: palette.text,
      }}
    >
      {!signedIn ? (
        <Stack.Screen name="SignIn" component={SignInScreen} options={{ headerShown: false }} />
      ) : (
        <>
          <Stack.Screen name="Tabs" component={Tabs} options={{ headerShown: false }} />
          <Stack.Screen name="AddItem" component={AddItemScreen} options={{ title: "Add item" }} />
          <Stack.Screen name="ItemDetail" component={ItemDetailScreen} options={{ title: "Item" }} />
          <Stack.Screen name="AddMember" component={AddMemberScreen} options={{ title: "Add family member" }} />
          <Stack.Screen
            name="OutfitDetail"
            component={OutfitDetailScreen}
            options={{ title: "Outfit" }}
          />
          <Stack.Screen name="Gaps" component={GapsScreen} options={{ title: "Closet gaps" }} />
          <Stack.Screen
            name="BasePhoto"
            component={BasePhotoScreen}
            options={{ title: "Your photo" }}
          />
          <Stack.Screen
            name="StylePreference"
            component={StylePreferenceScreen}
            options={{ title: "Default style" }}
          />
        </>
      )}
    </Stack.Navigator>
  );
}
