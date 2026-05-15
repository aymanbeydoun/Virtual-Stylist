import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Text } from "react-native";

import { useAuth } from "@/state/auth";
import { useActiveProfile } from "@/state/profile";
import { palette } from "@/theme";
import { AddItemScreen } from "@/screens/Closet/AddItemScreen";
import { ClosetScreen } from "@/screens/Closet/ClosetScreen";
import { ItemDetailScreen } from "@/screens/Closet/ItemDetailScreen";
import { FamilyScreen } from "@/screens/Family/FamilyScreen";
import { AddMemberScreen } from "@/screens/Family/AddMemberScreen";
import { SignInScreen } from "@/screens/Auth/SignInScreen";
import { StyleScreen } from "@/screens/Style/StyleScreen";
import { OutfitDetailScreen } from "@/screens/Style/OutfitDetailScreen";
import { YouScreen } from "@/screens/You/YouScreen";

export type RootStackParamList = {
  Tabs: undefined;
  AddItem: undefined;
  ItemDetail: { itemId: string };
  AddMember: undefined;
  OutfitDetail: { outfitId: string };
  SignIn: undefined;
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator<RootStackParamList>();

function TabBarIcon({ label, focused }: { label: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 18, opacity: focused ? 1 : 0.5 }}>{label}</Text>
  );
}

function Tabs() {
  const isKidMode = useActiveProfile((s) => s.isKidMode);
  const activeColor = isKidMode ? palette.kidPrimary : palette.accent;
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: activeColor,
        tabBarInactiveTintColor: palette.textMuted,
        tabBarStyle: { backgroundColor: palette.background, borderTopColor: palette.surfaceAlt },
      }}
    >
      <Tab.Screen
        name="Closet"
        component={ClosetScreen}
        options={{ tabBarIcon: ({ focused }) => <TabBarIcon label="👚" focused={focused} /> }}
      />
      <Tab.Screen
        name="Style"
        component={StyleScreen}
        options={{ tabBarIcon: ({ focused }) => <TabBarIcon label="✨" focused={focused} /> }}
      />
      <Tab.Screen
        name="Family"
        component={FamilyScreen}
        options={{ tabBarIcon: ({ focused }) => <TabBarIcon label="👪" focused={focused} /> }}
      />
      <Tab.Screen
        name="You"
        component={YouScreen}
        options={{ tabBarIcon: ({ focused }) => <TabBarIcon label="👤" focused={focused} /> }}
      />
    </Tab.Navigator>
  );
}

export function RootNavigator() {
  const signedIn = useAuth((s) => s.devUserId !== null);
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
        </>
      )}
    </Stack.Navigator>
  );
}
